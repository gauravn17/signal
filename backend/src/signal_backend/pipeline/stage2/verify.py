"""
Stage 2: deep verification, run only against the Stage 1 shortlist.

Agentic — the model decides what to investigate next per candidate based on
what it has already found (e.g. no GitHub -> check personal site; sparse
GitHub -> look at commit history; a specific claim -> attempt to verify it).
Produces cross-referenced findings, flagged disagreements between sources,
and an evidence-confidence rating. Bottlenecked by GitHub API rate limits,
so this only runs at funneled scale (~50-150 candidates), not full volume.
"""

import json
from typing import Literal

from pydantic import BaseModel

from signal_backend.models import Candidate, EvidenceConfidence, JobDescription, MatchResult, PipelineStage
from signal_backend.services.github import GitHubClient, get_github_client
from signal_backend.services.llm import LLMClient, get_llm_client
from signal_backend.services.website import check_website

SYSTEM_PROMPT = """You are deeply verifying one shortlisted candidate's resume claims
against live evidence before a hiring manager reviews them.

You have tools to check the candidate's GitHub profile/repos, a specific repo's
commit history, and their personal website. Investigate branching on what you find:
if there's no GitHub URL, try the website instead; if GitHub exists but looks sparse,
pull commit history on their most relevant repo; if the resume makes a specific,
checkable claim (an employer, a date range, a project), try to verify it with the
tools available. Call at most a few tools — do not over-investigate.

When you're done investigating, respond with JSON only, matching this schema:
{
  "findings": [{"text": str, "source": "resume" | "github" | "website", "supports_or_contradicts": "supports" | "contradicts" | "neutral"}],
  "disagreements": [{"topic": str, "resume_claim": str, "evidence_found": str}],
  "evidence_confidence": "thin" | "moderate" | "strong",
  "fit_summary": str
}

evidence_confidence reflects how much external corroboration you found, not fit:
"thin" = resume-only, no GitHub/site evidence available or reachable; "moderate" =
partial corroboration; "strong" = multiple independent sources agree. A thin-evidence
candidate is not a worse candidate — say so plainly in fit_summary, don't penalize.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_github_profile",
            "description": "Fetch a GitHub user's profile and public repos to verify technical claims and activity.",
            "parameters": {
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_github_commits",
            "description": "Fetch commit history for a specific repo to check authorship and activity timeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "author": {"type": "string"},
                },
                "required": ["owner", "repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_website",
            "description": "Check whether the candidate's personal website is live and read its content.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


class FindingItem(BaseModel):
    text: str
    source: Literal["resume", "github", "website"]
    supports_or_contradicts: Literal["supports", "contradicts", "neutral"]


class DisagreementItem(BaseModel):
    topic: str
    resume_claim: str
    evidence_found: str


class Stage2Response(BaseModel):
    findings: list[FindingItem]
    disagreements: list[DisagreementItem]
    evidence_confidence: Literal["thin", "moderate", "strong"]
    fit_summary: str


def _summarize_profile(user: dict) -> dict:
    return {
        "login": user.get("login"),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "public_repos": user.get("public_repos"),
        "followers": user.get("followers"),
        "created_at": user.get("created_at"),
    }


def _summarize_repo(repo: dict) -> dict:
    return {
        "name": repo.get("name"),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "fork": repo.get("fork"),
        "stargazers_count": repo.get("stargazers_count"),
        "pushed_at": repo.get("pushed_at"),
    }


def _summarize_commit(commit: dict) -> dict:
    commit_info = commit.get("commit", {})
    return {
        "sha": (commit.get("sha") or "")[:7],
        "author": commit_info.get("author", {}).get("name"),
        "date": commit_info.get("author", {}).get("date"),
        "message": (commit_info.get("message") or "").splitlines()[0][:200],
    }


def _make_tool_executor(github_client: GitHubClient, website_http_client=None):
    """Tool results are trimmed to the fields the model actually needs — raw
    GitHub API responses are large enough (nested owner objects, permissions,
    topics, etc. per repo) to blow through small-model token-per-minute
    limits on anything but a trivial profile."""

    def tool_executor(name: str, args: dict) -> str:
        if name == "check_github_profile":
            user = github_client.get_user(args["username"])
            if user is None:
                return "GitHub user not found."
            repos = github_client.get_user_repos(args["username"])
            return json.dumps(
                {"profile": _summarize_profile(user), "repos": [_summarize_repo(r) for r in repos[:10]]}
            )
        if name == "check_github_commits":
            commits = github_client.get_repo_commits(args["owner"], args["repo"], args.get("author"))
            return json.dumps({"commits": [_summarize_commit(c) for c in commits[:10]]})
        if name == "check_website":
            result = check_website(args["url"], http_client=website_http_client)
            if not result.is_live:
                return f"Website unreachable (status={result.status_code})."
            return (result.content or "")[:2000]
        return f"Unknown tool: {name}"

    return tool_executor


def run_stage2(
    candidate: Candidate,
    job_description: JobDescription,
    stage1_result: MatchResult,
    llm_client: LLMClient | None = None,
    github_client: GitHubClient | None = None,
    website_http_client=None,
    max_tool_calls: int = 5,
) -> MatchResult:
    llm_client = llm_client or get_llm_client()
    github_client = github_client or get_github_client()

    user_prompt = (
        f"Job requirements:\n{job_description.requirements}\n\n"
        f"Resume:\n{candidate.resume_raw_text}\n\n"
        f"Stage 1 extracted fields:\n{candidate.extracted_fields}\n\n"
        f"Stage 1 fit summary:\n{stage1_result.fit_summary}\n\n"
        f"GitHub URL: {candidate.github_url or 'none provided'}\n"
        f"Personal website: {candidate.website_url or 'none provided'}"
    )

    response = llm_client.agentic_run(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        tools=TOOLS,
        tool_executor=_make_tool_executor(github_client, website_http_client),
        response_model=Stage2Response,
        max_steps=max_tool_calls,
    )

    return MatchResult(
        candidate_id=candidate.id,
        job_description_id=job_description.id,
        stage=PipelineStage.stage2_verification,
        fit_summary=response.fit_summary,
        evidence_confidence=EvidenceConfidence(response.evidence_confidence),
        findings=[f.model_dump() for f in response.findings],
        disagreements=[d.model_dump() for d in response.disagreements],
    )
