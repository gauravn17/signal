from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from signal_backend.db.session import get_session
from signal_backend.models import Candidate, JobDescription, MatchResult
from signal_backend.pipeline.stage1.extract import run_stage1
from signal_backend.services.resume_parser import extract_resume_text

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CandidateWithMatch(BaseModel):
    candidate: Candidate
    match_result: MatchResult


@router.post("", response_model=CandidateWithMatch)
def create_candidate(
    job_description_id: UUID = Form(...),
    name: str = Form(...),
    email: str | None = Form(None),
    github_url: str | None = Form(None),
    website_url: str | None = Form(None),
    resume: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    jd = session.get(JobDescription, job_description_id)
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    resume_raw_text = extract_resume_text(resume.filename, resume.file.read())

    candidate = Candidate(
        job_description_id=jd.id,
        name=name,
        email=email,
        github_url=github_url,
        website_url=website_url,
        resume_raw_text=resume_raw_text,
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    match_result = run_stage1(candidate, jd)
    session.add(candidate)  # persist extracted_fields set by run_stage1
    session.add(match_result)
    session.commit()
    session.refresh(candidate)
    session.refresh(match_result)

    return CandidateWithMatch(candidate=candidate, match_result=match_result)


@router.get("", response_model=list[Candidate])
def list_candidates(job_description_id: UUID, session: Session = Depends(get_session)):
    return session.exec(select(Candidate).where(Candidate.job_description_id == job_description_id)).all()
