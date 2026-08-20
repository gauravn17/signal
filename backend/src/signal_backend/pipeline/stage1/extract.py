"""
Stage 1: cheap bulk pass, run against every candidate.

Non-agentic — one fixed structured-output LLM call per resume: extract fields
and do basic matching against the JD's structured requirements. No branching,
no external API calls (no GitHub/site lookups here). Must be cheap enough to
run over thousands of candidates.
"""

from signal_backend.models import Candidate, JobDescription, MatchResult


def run_stage1(candidate: Candidate, job_description: JobDescription) -> MatchResult:
    raise NotImplementedError
