from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from signal_backend.db.session import get_session
from signal_backend.models import JobDescription
from signal_backend.pipeline.stage1.parse_jd import parse_job_description

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


class JobDescriptionCreate(BaseModel):
    title: str
    raw_text: str


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
