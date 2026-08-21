"""
RQ job entry points. Each job opens its own DB session since it may run in
a separate worker process — nothing here can assume the API request's
session is available.
"""

from uuid import UUID

from sqlmodel import Session

from signal_backend.db.session import engine
from signal_backend.models import Candidate, JobDescription
from signal_backend.services.stage2_service import run_and_persist_stage2


def verify_candidate_job(candidate_id: str) -> str:
    """Runs Stage 2 for one candidate. Returns the created MatchResult's id (str)."""
    with Session(engine, expire_on_commit=False) as session:
        candidate = session.get(Candidate, UUID(candidate_id))
        jd = session.get(JobDescription, candidate.job_description_id)
        match_result = run_and_persist_stage2(session, candidate, jd)
        return str(match_result.id)
