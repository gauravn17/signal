from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from signal_backend.db.session import get_session
from signal_backend.jobs import verify_candidate_job
from signal_backend.models import Candidate, JobDescription, MatchResult, User
from signal_backend.pipeline.stage1.extract import run_stage1
from signal_backend.services.auth import get_current_user
from signal_backend.services.queue import get_stage2_queue
from signal_backend.services.resume_parser import extract_resume_text
from signal_backend.services.stage2_service import get_latest_stage1_result

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CandidateWithMatch(BaseModel):
    candidate: Candidate
    match_result: MatchResult


class CandidateDetail(BaseModel):
    candidate: Candidate
    match_results: list[MatchResult]


class VerifyJobResponse(BaseModel):
    job_id: str
    status: str


def _get_org_scoped_candidate(session: Session, candidate_id: UUID, current_user: User) -> Candidate:
    candidate = session.exec(
        select(Candidate).where(Candidate.id == candidate_id, Candidate.organization_id == current_user.organization_id)
    ).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.post("", response_model=CandidateWithMatch)
def create_candidate(
    job_description_id: UUID = Form(...),
    name: str | None = Form(None),
    email: str | None = Form(None),
    github_url: str | None = Form(None),
    website_url: str | None = Form(None),
    resume: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """name/email/github_url/website_url are optional overrides — Stage 1
    extracts them from the resume itself when not provided, so uploading
    many candidates doesn't require typing in contact info by hand."""
    jd = session.exec(
        select(JobDescription).where(
            JobDescription.id == job_description_id, JobDescription.organization_id == current_user.organization_id
        )
    ).first()
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    resume_raw_text = extract_resume_text(resume.filename, resume.file.read())

    candidate = Candidate(
        organization_id=current_user.organization_id,
        job_description_id=jd.id,
        name=name,
        email=email,
        github_url=github_url,
        website_url=website_url,
        resume_raw_text=resume_raw_text,
    )

    match_result = run_stage1(candidate, jd)
    candidate.name = candidate.name or "Unnamed Candidate"

    session.add(candidate)
    session.add(match_result)
    session.commit()
    session.refresh(candidate)
    session.refresh(match_result)

    return CandidateWithMatch(candidate=candidate, match_result=match_result)


@router.get("", response_model=list[Candidate])
def list_candidates(
    job_description_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return session.exec(
        select(Candidate).where(
            Candidate.job_description_id == job_description_id,
            Candidate.organization_id == current_user.organization_id,
        )
    ).all()


@router.get("/{candidate_id}", response_model=CandidateDetail)
def get_candidate(
    candidate_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    candidate = _get_org_scoped_candidate(session, candidate_id, current_user)
    match_results = session.exec(
        select(MatchResult).where(MatchResult.candidate_id == candidate_id).order_by(MatchResult.created_at)
    ).all()
    return CandidateDetail(candidate=candidate, match_results=match_results)


@router.post("/{candidate_id}/verify", response_model=VerifyJobResponse)
def verify_candidate(
    candidate_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Enqueues Stage 2 verification (the bottlenecked, GitHub-rate-limited
    stage) onto the background job queue rather than running it inline.
    Poll GET /jobs/{job_id} for the result."""
    _get_org_scoped_candidate(session, candidate_id, current_user)

    if get_latest_stage1_result(session, candidate_id) is None:
        raise HTTPException(status_code=400, detail="Stage 1 must run before Stage 2 verification")

    job = get_stage2_queue().enqueue(verify_candidate_job, str(candidate_id))
    return VerifyJobResponse(job_id=job.id, status=job.get_status())
