from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from signal_backend.api.candidates import VerifyJobResponse
from signal_backend.db.session import get_session
from signal_backend.jobs import verify_candidate_job
from signal_backend.models import Candidate, JobDescription, User
from signal_backend.pipeline.stage1.parse_jd import parse_job_description
from signal_backend.services.auth import get_current_user
from signal_backend.services.queue import get_stage2_queue
from signal_backend.services.stage2_service import get_latest_stage1_result

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


class JobDescriptionCreate(BaseModel):
    title: str
    raw_text: str


class ShortlistRequest(BaseModel):
    candidate_ids: list[UUID]


def _get_org_scoped_jd(session: Session, jd_id: UUID, current_user: User) -> JobDescription:
    jd = session.exec(
        select(JobDescription).where(
            JobDescription.id == jd_id, JobDescription.organization_id == current_user.organization_id
        )
    ).first()
    if jd is None:
        # Same 404 whether the id doesn't exist or belongs to another org —
        # never reveal that another tenant's data exists.
        raise HTTPException(status_code=404, detail="Job description not found")
    return jd


@router.post("", response_model=JobDescription)
def create_job_description(
    payload: JobDescriptionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    requirements = parse_job_description(payload.raw_text)
    jd = JobDescription(
        organization_id=current_user.organization_id,
        title=payload.title,
        raw_text=payload.raw_text,
        requirements=requirements,
    )
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return jd


@router.get("", response_model=list[JobDescription])
def list_job_descriptions(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    return session.exec(
        select(JobDescription)
        .where(JobDescription.organization_id == current_user.organization_id)
        .order_by(JobDescription.created_at.desc())
    ).all()


@router.get("/{jd_id}", response_model=JobDescription)
def get_job_description(
    jd_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    return _get_org_scoped_jd(session, jd_id, current_user)


@router.post("/{jd_id}/shortlist", response_model=list[VerifyJobResponse])
def shortlist_candidates(
    jd_id: UUID,
    payload: ShortlistRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Enqueues Stage 2 verification for a hiring manager's picked subset of
    Stage 1 candidates. Poll GET /jobs/{job_id} per candidate for results."""
    jd = _get_org_scoped_jd(session, jd_id, current_user)

    queue = get_stage2_queue()
    responses = []
    for candidate_id in payload.candidate_ids:
        candidate = session.get(Candidate, candidate_id)
        if (
            candidate is None
            or candidate.job_description_id != jd.id
            or candidate.organization_id != current_user.organization_id
        ):
            raise HTTPException(status_code=400, detail=f"Candidate {candidate_id} not found for this job description")
        if get_latest_stage1_result(session, candidate_id) is None:
            raise HTTPException(status_code=400, detail=f"Candidate {candidate_id} has no Stage 1 result")
        job = queue.enqueue(verify_candidate_job, str(candidate_id))
        responses.append(VerifyJobResponse(job_id=job.id, status=job.get_status()))
    return responses
