"""
Stage 1: cheap bulk pass, run against every candidate.

Non-agentic — one fixed structured-output LLM call per resume: extract fields
and do basic matching against the JD's structured requirements. No branching,
no external API calls (no GitHub/site lookups here). Must be cheap enough to
run over thousands of candidates.
"""

from typing import Literal

from pydantic import BaseModel

from signal_backend.models import Candidate, JobDescription, MatchResult, PipelineStage
from signal_backend.services.llm import LLMClient, get_llm_client

SYSTEM_PROMPT = """You are screening a candidate's resume against a job description's
structured requirements.

First, extract the candidate's contact info from the resume itself (name, email,
GitHub URL, personal website URL) — resumes typically list these in the header.
Use null for anything not present; do not guess or invent a value.

Then extract key resume fields, and evaluate the resume against each requirement
listed in the user message. For each requirement, note whether the resume meets it
("yes", "partial", "no") and cite the specific evidence in the resume text. Write a
short, plain-language fit summary — do not produce a numeric score.

Respond with JSON only, matching this schema:
{
  "contact_info": {
    "name": str | null,
    "email": str | null,
    "github_url": str | null,
    "website_url": str | null
  },
  "extracted_fields": {
    "years_experience": number | null,
    "skills": [str],
    "employment_history": [{"company": str, "title": str, "start_date": str | null, "end_date": str | null}],
    "education": [str]
  },
  "requirement_matches": [
    {"requirement_text": str, "category": "must_have" | "nice_to_have", "met": "yes" | "partial" | "no", "evidence": str}
  ],
  "fit_summary": str
}
"""


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    github_url: str | None = None
    website_url: str | None = None


class EmploymentEntry(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None


class ExtractedFields(BaseModel):
    years_experience: float | None = None
    skills: list[str]
    employment_history: list[EmploymentEntry]
    education: list[str]


class RequirementMatch(BaseModel):
    requirement_text: str
    category: Literal["must_have", "nice_to_have"]
    met: Literal["yes", "partial", "no"]
    evidence: str


class Stage1Response(BaseModel):
    contact_info: ContactInfo
    extracted_fields: ExtractedFields
    requirement_matches: list[RequirementMatch]
    fit_summary: str


def _with_scheme(url: str | None) -> str | None:
    """Resumes often list URLs without a protocol (e.g. "github.com/jane")
    — normalize so they render as clickable links rather than relative paths."""
    if url and not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def run_stage1(
    candidate: Candidate,
    job_description: JobDescription,
    llm_client: LLMClient | None = None,
) -> MatchResult:
    llm_client = llm_client or get_llm_client()

    user_prompt = (
        f"Requirements:\n{job_description.requirements}\n\n"
        f"Resume:\n{candidate.resume_raw_text}"
    )
    response = llm_client.structured_complete(
        system=SYSTEM_PROMPT, user=user_prompt, response_model=Stage1Response
    )

    candidate.extracted_fields = response.extracted_fields.model_dump()
    # Manual form values (if provided) win; otherwise fall back to what the
    # resume itself says — most candidates won't be typed in one at a time.
    candidate.name = candidate.name or response.contact_info.name
    candidate.email = candidate.email or response.contact_info.email
    candidate.github_url = _with_scheme(candidate.github_url or response.contact_info.github_url)
    candidate.website_url = _with_scheme(candidate.website_url or response.contact_info.website_url)

    return MatchResult(
        candidate_id=candidate.id,
        job_description_id=job_description.id,
        stage=PipelineStage.stage1_bulk,
        fit_summary=response.fit_summary,
        findings=[m.model_dump() for m in response.requirement_matches],
    )
