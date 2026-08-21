import httpx

from signal_backend.models import Candidate, EvidenceConfidence, JobDescription, MatchResult, PipelineStage
from signal_backend.pipeline.stage2.verify import run_stage2
from signal_backend.services.github import GitHubClient


class ScriptedLLMClient:
    """Bypasses real model reasoning: executes a fixed tool-call script, then
    returns a canned final answer. Lets us test tool wiring + result mapping
    without depending on real (or even fake-reasoning) model behavior."""

    def __init__(self, tool_calls_to_make, final_response):
        self.tool_calls_to_make = tool_calls_to_make
        self.final_response = final_response
        self.executed = []

    def agentic_run(self, system, user, tools, tool_executor, response_model, max_steps=5):
        for name, args in self.tool_calls_to_make:
            result = tool_executor(name, args)
            self.executed.append((name, args, result))
        return response_model.model_validate(self.final_response)


def _github_client_with_handler(handler) -> GitHubClient:
    return GitHubClient(
        http_client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    )


def _website_client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _candidate_and_jd(**candidate_kwargs):
    jd = JobDescription(title="Backend Engineer", raw_text="...", requirements=[])
    candidate = Candidate(
        job_description_id=jd.id, name="Jane Doe", resume_raw_text="Jane Doe resume text", **candidate_kwargs
    )
    stage1_result = MatchResult(
        candidate_id=candidate.id, job_description_id=jd.id, stage=PipelineStage.stage1_bulk, fit_summary="ok"
    )
    return candidate, jd, stage1_result


def test_run_stage2_calls_github_profile_tool_and_maps_result():
    def handler(request):
        if request.url.path == "/users/janedoe":
            return httpx.Response(200, json={"login": "janedoe", "public_repos": 12})
        if request.url.path == "/users/janedoe/repos":
            return httpx.Response(200, json=[{"name": "cool-project", "pushed_at": "2024-06-01T00:00:00Z"}])
        return httpx.Response(404)

    candidate, jd, stage1_result = _candidate_and_jd(github_url="https://github.com/janedoe")

    llm_client = ScriptedLLMClient(
        tool_calls_to_make=[("check_github_profile", {"username": "janedoe"})],
        final_response={
            "findings": [
                {
                    "text": "GitHub shows active repos matching claimed skills",
                    "source": "github",
                    "supports_or_contradicts": "supports",
                }
            ],
            "disagreements": [],
            "evidence_confidence": "strong",
            "fit_summary": "Strong, verified match.",
        },
    )

    match_result = run_stage2(
        candidate, jd, stage1_result, llm_client=llm_client, github_client=_github_client_with_handler(handler)
    )

    assert llm_client.executed[0][0] == "check_github_profile"
    assert "janedoe" in llm_client.executed[0][2]
    assert match_result.stage == PipelineStage.stage2_verification
    assert match_result.evidence_confidence == EvidenceConfidence.strong
    assert match_result.fit_summary == "Strong, verified match."
    assert match_result.findings[0]["source"] == "github"


def test_run_stage2_falls_back_to_website_when_no_github():
    def handler(request):
        return httpx.Response(200, text="Jane Doe — Software Engineer portfolio")

    candidate, jd, stage1_result = _candidate_and_jd(website_url="https://janedoe.dev")

    llm_client = ScriptedLLMClient(
        tool_calls_to_make=[("check_website", {"url": "https://janedoe.dev"})],
        final_response={
            "findings": [{"text": "Personal site is live and matches resume framing", "source": "website", "supports_or_contradicts": "supports"}],
            "disagreements": [],
            "evidence_confidence": "moderate",
            "fit_summary": "Reasonable corroboration via personal site.",
        },
    )

    match_result = run_stage2(
        candidate,
        jd,
        stage1_result,
        llm_client=llm_client,
        github_client=_github_client_with_handler(lambda r: httpx.Response(404)),
        website_http_client=_website_client_with_handler(handler),
    )

    assert llm_client.executed[0][0] == "check_website"
    assert "Jane Doe" in llm_client.executed[0][2]
    assert match_result.evidence_confidence == EvidenceConfidence.moderate


def test_run_stage2_thin_evidence_not_penalized_in_summary():
    candidate, jd, stage1_result = _candidate_and_jd()  # no github_url, no website_url

    llm_client = ScriptedLLMClient(
        tool_calls_to_make=[],
        final_response={
            "findings": [],
            "disagreements": [],
            "evidence_confidence": "thin",
            "fit_summary": "No external evidence available; resume-only assessment.",
        },
    )

    match_result = run_stage2(
        candidate, jd, stage1_result, llm_client=llm_client, github_client=_github_client_with_handler(lambda r: httpx.Response(404))
    )

    assert match_result.evidence_confidence == EvidenceConfidence.thin
    assert "resume-only" in match_result.fit_summary
