from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from signal_backend.db.session import get_session
from signal_backend.models import Candidate, JobDescription, MatchResult, PipelineStage
from signal_backend.pipeline.stage1.extract import run_stage1
from signal_backend.pipeline.stage2.verify import run_stage2
from signal_backend.services.resume_parser import extract_resume_text

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CandidateWithMatch(BaseModel):
    candidate: Candidate
    match_result: MatchResult


class CandidateDetail(BaseModel):
    candidate: Candidate
    match_results: list[MatchResult]


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


@router.get("/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: UUID, session: Session = Depends(get_session)):
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    match_results = session.exec(
        select(MatchResult).where(MatchResult.candidate_id == candidate_id).order_by(MatchResult.created_at)
    ).all()
    return CandidateDetail(candidate=candidate, match_results=match_results)


@router.post("/{candidate_id}/verify", response_model=MatchResult)
def verify_candidate(candidate_id: UUID, session: Session = Depends(get_session)):
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    jd = session.get(JobDescription, candidate.job_description_id)

    stage1_result = session.exec(
        select(MatchResult)
        .where(MatchResult.candidate_id == candidate_id, MatchResult.stage == PipelineStage.stage1_bulk)
        .order_by(MatchResult.created_at.desc())
    ).first()
    if stage1_result is None:
        raise HTTPException(status_code=400, detail="Stage 1 must run before Stage 2 verification")

    match_result = run_stage2(candidate, jd, stage1_result)
    session.add(match_result)
    session.commit()
    session.refresh(match_result)
    return match_result
