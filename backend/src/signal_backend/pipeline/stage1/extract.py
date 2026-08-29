"""
Stage 1: cheap bulk pass, run against every candidate.

Non-agentic — one fixed structured-output LLM call per resume: extract a
full candidate profile and holistically evaluate the resume against each of
the JD's already-classified requirements. No branching, no external API
calls (no GitHub/site lookups here). Must be cheap enough to run over
thousands of candidates.

Requirement identity (requirement_id, category, requirement_type) is owned
by the JD (see pipeline/stage1/parse_jd.py), never re-derived here — the
model receives the canonical requirement list in a fixed order and returns
assessments in that same order; we map by position, not by asking the model
to reproduce requirement text.
"""

import logging
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from signal_backend.models import Candidate, EvidenceConfidence, JobDescription, MatchResult, PipelineStage
from signal_backend.services.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are holistically evaluating a candidate's resume against a job
description's requirements, for a hiring manager who will make the final decision.
This is not keyword matching — a bare mention of a skill is not the same as
demonstrated, sustained, professional use of it. For example, a resume saying
"Kafka project" is not equivalent to "3 years designing and operating Kafka
infrastructure in production" — the assessment and evidence must reflect that
difference, not just the presence of the word "Kafka".

First, extract the candidate's contact info from the resume itself (name, email,
GitHub URL, personal website URL). Use null for anything not present; do not guess
or invent a value.

Then extract the candidate's full profile from the resume: skills, employment
history (with responsibilities per role), education, certifications, projects, and
domain experience (e.g. fintech, healthcare, ML infra). Extract only what the resume
actually states.

Then evaluate the candidate against EACH requirement listed below, in the exact
order given. Return exactly one assessment per requirement, in that same order —
position is how assessments are matched back to requirements, so do not skip,
merge, or reorder them. Each requirement is labeled with its type, which
determines which fields are relevant:

- type "experience", "skill", or "leadership" -> produce an experience-shaped
  assessment, with "kind" set to that exact same type value ("experience",
  "skill", or "leadership" — whichever the requirement was labeled): assessment
  level, depth, duration, recency, context, ownership, scale, impact, seniority,
  evidence, gaps.
- type "education" -> produce an education-shaped assessment: assessment level
  (met/partially_met/not_met/unclear), degree_level, field_of_study, institution,
  evidence, gaps.
- type "certification" -> produce a certification-shaped assessment: assessment
  level (met/not_met/unclear), certification_name, issuer, status_or_date,
  evidence, gaps.
- type "other" -> produce a general assessment: assessment level, free-text notes,
  evidence, gaps.

For experience/skill/leadership assessments:
- assessment: "strong" | "moderate" | "weak" | "not_demonstrated". "not_demonstrated"
  means the resume gives no evidence for it — this is common and is not a red flag
  by itself.
- context: "professional" | "internship" | "academic" | "personal" | "unknown" — a
  requirement demonstrated only through a personal/class project is real evidence,
  but is not the same strength as sustained professional use; reflect that in the
  assessment level itself, not just the context label.
- duration, recency, ownership, scale, impact: leave null if the resume doesn't
  state or clearly imply it. Do not estimate or invent a number that isn't in the
  resume.
- seniority: must be derived from the depth/ownership/scale/duration you already
  found and the quoted evidence — never assert seniority from a job title alone
  (e.g. a "Senior Engineer" title does not by itself mean strong seniority for a
  specific requirement; look for what they actually did).
- evidence: ALWAYS a JSON array of objects, even for a single quote — never a
  plain string. Each object is {"excerpt": "...", "source": "resume"}. Empty
  array ([]) if not_demonstrated, never an empty string or omitted field.
- gaps: specific things you could not determine for this requirement from the
  resume alone.

Universal rules:
- Never treat a bare keyword mention as equivalent to demonstrated professional
  experience.
- Never infer a fact that isn't stated or clearly implied — prefer leaving a field
  null and noting it in gaps over guessing.
- Never let a missing detail (e.g. no duration stated) by itself lower the
  assessment level beyond what the actually-described experience supports — note
  it as a gap instead of penalizing for it.
- Do not score education/certifications by prestige — only by relevance to what
  the requirement actually asks for.

Finally, produce:
- strengths: the candidate's clearest strengths for this specific role (not
  generic praise).
- gaps: the candidate's clearest gaps or open questions for this specific role.
- evidence_confidence: "thin" | "moderate" | "strong" — how much specific,
  concrete detail the resume itself provides (regardless of fit). A resume with
  vague, generic bullet points is "thin" evidence even if it lists the right
  keywords; a resume with specific, detailed, quantified claims is "strong"
  evidence. This is independent of fit in both directions — a strong-fit
  candidate can have thin evidence, and a moderate-fit candidate can have strong
  evidence. Do not conflate the two.
- fit_summary: a short, plain-language overall summary of fit for a hiring
  manager. Do not produce a numeric score.

Respond with JSON only, matching this schema:
{
  "contact_info": {"name": str|null, "email": str|null, "github_url": str|null, "website_url": str|null},
  "extracted_fields": {
    "years_experience": number|null,
    "skills": [str],
    "employment_history": [{"company": str, "title": str, "start_date": str|null, "end_date": str|null, "responsibilities": [str]}],
    "education": [str],
    "certifications": [str],
    "projects": [{"name": str, "description": str, "technologies": [str]}],
    "domain_experience": [str]
  },
  "requirement_assessments": [
    {
      "requirement_id": str|null,
      "assessment": {
        "kind": "experience"|"skill"|"leadership"|"education"|"certification"|"other",
        ... fields matching that kind, as described above ...
      }
    }
  ],
  "strengths": [str],
  "gaps": [str],
  "evidence_confidence": "thin"|"moderate"|"strong",
  "fit_summary": str
}

requirement_id is optional — if you include it, it must be the id of the
requirement at that position, used only to double-check alignment. It is never
a substitute for returning assessments in the given order.

Worked example of ONE fully-formed assessment (note evidence is always an
array, never a string, and kind matches the requirement's exact labeled type):
{
  "requirement_id": "req_001",
  "assessment": {
    "kind": "experience",
    "assessment": "strong",
    "depth": "high",
    "duration": "3 years",
    "recency": "current role",
    "context": "professional",
    "ownership": "designed and owned the system end to end",
    "scale": "20 million events per day",
    "impact": "reduced processing latency by 30%",
    "seniority": "led architecture decisions independently, per described ownership",
    "evidence": [
      {"excerpt": "Designed and operated a Kafka-based event pipeline processing 20M events/day", "source": "resume"}
    ],
    "gaps": []
  }
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
    responsibilities: list[str] = []


class ProjectEntry(BaseModel):
    name: str
    description: str
    technologies: list[str] = []


class ExtractedFields(BaseModel):
    years_experience: float | None = None
    skills: list[str]
    employment_history: list[EmploymentEntry]
    education: list[str]
    certifications: list[str] = []
    projects: list[ProjectEntry] = []
    domain_experience: list[str] = []


class Evidence(BaseModel):
    excerpt: str
    source: Literal["resume", "application"]


class ExperienceAssessment(BaseModel):
    """Covers requirement_type "experience", "skill", and "leadership" — they
    share the same meaningful dimensions (see design discussion: leadership is
    "led a team of 6 engineers" captured via scope/ownership/evidence, not a
    separate schema)."""

    # The model naturally echoes back whichever of these three types it was
    # told the requirement was (see _build_requirements_block) rather than
    # normalizing to one literal — found empirically against the real model,
    # not assumed. Pydantic discriminated unions support a multi-value
    # Literal on one variant, so this is accommodated rather than fought.
    kind: Literal["experience", "skill", "leadership"]
    assessment: Literal["strong", "moderate", "weak", "not_demonstrated"]
    depth: str | None = None
    duration: str | None = None
    recency: str | None = None
    context: Literal["professional", "internship", "academic", "personal", "unknown"] | None = None
    ownership: str | None = None
    scale: str | None = None
    impact: str | None = None
    seniority: str | None = None
    evidence: list[Evidence] = []
    gaps: list[str] = []


class EducationAssessment(BaseModel):
    kind: Literal["education"] = "education"
    assessment: Literal["met", "partially_met", "not_met", "unclear"]
    degree_level: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    evidence: list[Evidence] = []
    gaps: list[str] = []


class CertificationAssessment(BaseModel):
    kind: Literal["certification"] = "certification"
    assessment: Literal["met", "not_met", "unclear"]
    certification_name: str | None = None
    issuer: str | None = None
    status_or_date: str | None = None
    evidence: list[Evidence] = []
    gaps: list[str] = []


class GeneralAssessment(BaseModel):
    kind: Literal["other"] = "other"
    assessment: Literal["strong", "moderate", "weak", "not_demonstrated", "met", "not_met", "unclear"]
    notes: str | None = None
    evidence: list[Evidence] = []
    gaps: list[str] = []


AssessmentUnion = Annotated[
    Union[ExperienceAssessment, EducationAssessment, CertificationAssessment, GeneralAssessment],
    Field(discriminator="kind"),
]


class RequirementAssessmentItem(BaseModel):
    # Optional, consistency-check only — position in the list is authoritative,
    # never this field. See module docstring.
    requirement_id: str | None = None
    assessment: AssessmentUnion


class Stage1Response(BaseModel):
    contact_info: ContactInfo
    extracted_fields: ExtractedFields
    requirement_assessments: list[RequirementAssessmentItem]
    strengths: list[str]
    gaps: list[str]
    evidence_confidence: Literal["thin", "moderate", "strong"]
    fit_summary: str


def _with_scheme(url: str | None) -> str | None:
    """Resumes often list URLs without a protocol (e.g. "github.com/jane")
    — normalize so they render as clickable links rather than relative paths."""
    if url and not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def _build_requirements_block(requirements: list[dict]) -> str:
    lines = []
    for req in requirements:
        lines.append(
            f"- id={req['requirement_id']} type={req['requirement_type']} "
            f"category={req['category']}: {req['text']}"
        )
    return "\n".join(lines)


def run_stage1(
    candidate: Candidate,
    job_description: JobDescription,
    llm_client: LLMClient | None = None,
) -> MatchResult:
    llm_client = llm_client or get_llm_client()

    requirements = job_description.requirements
    user_prompt = (
        f"Requirements (in order, evaluate and return exactly one assessment per requirement in this order):\n"
        f"{_build_requirements_block(requirements)}\n\n"
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

    findings = []
    if len(response.requirement_assessments) != len(requirements):
        logger.warning(
            "Stage 1 returned %d assessments for %d requirements (candidate %s) — "
            "positions beyond the shorter list are marked not_demonstrated.",
            len(response.requirement_assessments),
            len(requirements),
            candidate.id,
        )
    for i, req in enumerate(requirements):
        if i < len(response.requirement_assessments):
            item = response.requirement_assessments[i]
            if item.requirement_id is not None and item.requirement_id != req["requirement_id"]:
                logger.warning(
                    "Stage 1 assessment at position %d echoed requirement_id %r, expected %r "
                    "(candidate %s) — trusting position, not the echoed id.",
                    i,
                    item.requirement_id,
                    req["requirement_id"],
                    candidate.id,
                )
            assessment_dict = item.assessment.model_dump()
        else:
            assessment_dict = {
                "kind": "other",
                "assessment": "not_demonstrated",
                "notes": None,
                "evidence": [],
                "gaps": ["Stage 1 did not return an assessment for this requirement."],
            }
        findings.append(
            {
                "requirement_id": req["requirement_id"],
                "requirement_text": req["text"],
                "category": req["category"],
                "requirement_type": req["requirement_type"],
                "assessment": assessment_dict,
            }
        )

    return MatchResult(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id,
        job_description_id=job_description.id,
        stage=PipelineStage.stage1_bulk,
        fit_summary=response.fit_summary,
        evidence_confidence=EvidenceConfidence(response.evidence_confidence),
        findings=findings,
        assessment_details={"strengths": response.strengths, "gaps": response.gaps},
    )
