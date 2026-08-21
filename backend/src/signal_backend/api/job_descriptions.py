from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from signal_backend.api.candidates import run_and_persist_stage2
from signal_backend.db.session import get_session
from signal_backend.models import Candidate, JobDescription, MatchResult
from signal_backend.pipeline.stage1.parse_jd import parse_job_description

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


class JobDescriptionCreate(BaseModel):
    title: str
    raw_text: str


class ShortlistRequest(BaseModel):
    candidate_ids: list[UUID]


@router.post("", response_model=JobDescription)
def create_job_description(payload: JobDescriptionCreate, session: Session = Depends(get_session)):
    requirements = parse_job_description(payload.raw_text)
    jd = JobDescription(title=payload.title, raw_text=payload.raw_text, requirements=requirements)
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return jd


@router.get("/{jd_id}", response_model=JobDescription)
def get_job_description(jd_id: UUID, session: Session = Depends(get_session)):
    jd = session.get(JobDescription, jd_id)
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")
    return jd


@router.post("/{jd_id}/shortlist", response_model=list[MatchResult])
def shortlist_candidates(jd_id: UUID, payload: ShortlistRequest, session: Session = Depends(get_session)):
    """Runs Stage 2 verification for a hiring manager's picked subset of
    Stage 1 candidates. Synchronous for now — step 8 moves this onto a
    background job queue since Stage 2 is the bottlenecked stage."""
    jd = session.get(JobDescription, jd_id)
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    results = []
    for candidate_id in payload.candidate_ids:
        candidate = session.get(Candidate, candidate_id)
        if candidate is None or candidate.job_description_id != jd.id:
            raise HTTPException(status_code=400, detail=f"Candidate {candidate_id} not found for this job description")
        try:
            results.append(run_and_persist_stage2(session, candidate, jd))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return results
