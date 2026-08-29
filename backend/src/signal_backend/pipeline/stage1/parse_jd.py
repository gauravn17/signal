"""
Parses a raw job description into structured requirements, once per JD
(not per candidate). Cheap, non-agentic, single LLM call.

The JD is the source of truth for requirement identity: requirement_id,
category, and requirement_type are all fixed here and never re-derived per
candidate in Stage 1 — that would risk wasted repeated work and, worse,
inconsistent classification of the same requirement across candidates.
"""

from typing import Literal

from pydantic import BaseModel

from signal_backend.services.llm import LLMClient, get_llm_client

RequirementType = Literal["experience", "skill", "leadership", "education", "certification", "other"]

SYSTEM_PROMPT = """You are parsing a job description into structured hiring requirements.

Classify each requirement as "must_have" or "nice_to_have". Set source to
"hiring_team_free_text" for specific, team-idiosyncratic criteria that a generic
keyword filter would miss (e.g. "must have on-call experience", "prefers candidates
who've worked in a regulated industry"), and "generic" for standard role requirements
(e.g. "5+ years of experience", "proficient in Python").

Also classify each requirement's type — this determines how it will later be
evaluated against a candidate, so choose carefully:
- "experience": a role/domain/technology requirement demonstrated through work
  history (e.g. "distributed systems experience", "Kafka", "fintech background").
- "skill": a specific technical or professional skill (e.g. "proficient in Python",
  "SQL", "technical writing").
- "leadership": people-management, mentorship, or ownership/scope requirements
  (e.g. "led a team of engineers", "owned a product area").
- "education": a degree/field-of-study requirement.
- "certification": a named certification or license requirement.
- "other": anything that doesn't fit the above (e.g. "willingness to travel",
  "authorized to work in the US", "excellent communicator").

Respond with JSON only, matching this schema:
{"requirements": [{"text": str, "category": "must_have" | "nice_to_have", "source": "generic" | "hiring_team_free_text", "requirement_type": "experience" | "skill" | "leadership" | "education" | "certification" | "other"}]}
"""


class RequirementItem(BaseModel):
    text: str
    category: Literal["must_have", "nice_to_have"]
    source: Literal["generic", "hiring_team_free_text"]
    requirement_type: RequirementType


class ParsedJD(BaseModel):
    requirements: list[RequirementItem]


def parse_job_description(raw_text: str, llm_client: LLMClient | None = None) -> list[dict]:
    llm_client = llm_client or get_llm_client()
    parsed = llm_client.structured_complete(system=SYSTEM_PROMPT, user=raw_text, response_model=ParsedJD)
    # requirement_id is assigned here, not by the model — a plain sequential id
    # needs no LLM judgment, and doing it ourselves guarantees it's stable and
    # never duplicated.
    return [
        {"requirement_id": f"req_{i + 1:03d}", **item.model_dump()}
        for i, item in enumerate(parsed.requirements)
    ]
