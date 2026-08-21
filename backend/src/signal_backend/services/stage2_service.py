from uuid import UUID

from sqlmodel import Session, select

from signal_backend.models import Candidate, JobDescription, MatchResult, PipelineStage
from signal_backend.pipeline.stage2.verify import run_stage2


def get_latest_stage1_result(session: Session, candidate_id: UUID) -> MatchResult | None:
    return session.exec(
        select(MatchResult)
        .where(MatchResult.candidate_id == candidate_id, MatchResult.stage == PipelineStage.stage1_bulk)
        .order_by(MatchResult.created_at.desc())
    ).first()


def run_and_persist_stage2(session: Session, candidate: Candidate, jd: JobDescription) -> MatchResult:
    """Shared by the API's verify/shortlist endpoints and the RQ worker job.
    Raises ValueError if Stage 1 hasn't run yet — callers map that to a 400."""
    stage1_result = get_latest_stage1_result(session, candidate.id)
    if stage1_result is None:
        raise ValueError(f"Candidate {candidate.id} has no Stage 1 result; Stage 1 must run before Stage 2")

    match_result = run_stage2(candidate, jd, stage1_result)
    session.add(match_result)
    session.commit()
    session.refresh(match_result)
    return match_result
