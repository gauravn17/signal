"""
Parses a raw job description into structured requirements, once per JD
(not per candidate). Cheap, non-agentic, single LLM call.
"""

from typing import Literal

from pydantic import BaseModel

from signal_backend.services.llm import LLMClient, get_llm_client

SYSTEM_PROMPT = """You are parsing a job description into structured hiring requirements.

Classify each requirement as "must_have" or "nice_to_have". Set source to
"hiring_team_free_text" for specific, team-idiosyncratic criteria that a generic
keyword filter would miss (e.g. "must have on-call experience", "prefers candidates
who've worked in a regulated industry"), and "generic" for standard role requirements
(e.g. "5+ years of experience", "proficient in Python").

Respond with JSON only, matching this schema:
{"requirements": [{"text": str, "category": "must_have" | "nice_to_have", "source": "generic" | "hiring_team_free_text"}]}
"""


class RequirementItem(BaseModel):
    text: str
    category: Literal["must_have", "nice_to_have"]
    source: Literal["generic", "hiring_team_free_text"]


class ParsedJD(BaseModel):
    requirements: list[RequirementItem]


def parse_job_description(raw_text: str, llm_client: LLMClient | None = None) -> list[dict]:
    llm_client = llm_client or get_llm_client()
    parsed = llm_client.structured_complete(system=SYSTEM_PROMPT, user=raw_text, response_model=ParsedJD)
    return [item.model_dump() for item in parsed.requirements]
