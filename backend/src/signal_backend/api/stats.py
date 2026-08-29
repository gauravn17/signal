from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from signal_backend.db.session import get_session
from signal_backend.models import Candidate, JobDescription, MatchResult, PipelineStage

router = APIRouter(prefix="/stats", tags=["stats"])


class Stats(BaseModel):
    job_description_count: int
    candidate_count: int
    stage2_verified_count: int


@router.get("", response_model=Stats)
def get_stats(session: Session = Depends(get_session)):
    job_description_count = session.exec(select(func.count()).select_from(JobDescription)).one()
    candidate_count = session.exec(select(func.count()).select_from(Candidate)).one()
    stage2_verified_count = session.exec(
        select(func.count())
        .select_from(MatchResult)
        .where(MatchResult.stage == PipelineStage.stage2_verification)
    ).one()
    return Stats(
        job_description_count=job_description_count,
        candidate_count=candidate_count,
        stage2_verified_count=stage2_verified_count,
    )
