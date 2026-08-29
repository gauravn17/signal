from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from signal_backend.db.session import get_session
from signal_backend.models import Candidate, JobDescription, MatchResult, PipelineStage, User
from signal_backend.services.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])


class Stats(BaseModel):
    job_description_count: int
    candidate_count: int
    stage2_verified_count: int


@router.get("", response_model=Stats)
def get_stats(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    org_id = current_user.organization_id
    job_description_count = session.exec(
        select(func.count()).select_from(JobDescription).where(JobDescription.organization_id == org_id)
    ).one()
    candidate_count = session.exec(
        select(func.count()).select_from(Candidate).where(Candidate.organization_id == org_id)
    ).one()
    stage2_verified_count = session.exec(
        select(func.count())
        .select_from(MatchResult)
        .where(MatchResult.stage == PipelineStage.stage2_verification, MatchResult.organization_id == org_id)
    ).one()
    return Stats(
        job_description_count=job_description_count,
        candidate_count=candidate_count,
        stage2_verified_count=stage2_verified_count,
    )
