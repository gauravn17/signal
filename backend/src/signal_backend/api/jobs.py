from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlmodel import Session

from signal_backend.db.session import get_session
from signal_backend.models import MatchResult
from signal_backend.services.queue import get_redis_connection

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: MatchResult | None = None
    error: str | None = None


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, session: Session = Depends(get_session)):
    try:
        job = Job.fetch(job_id, connection=get_redis_connection())
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = None
    if job.is_finished:
        return_value = job.return_value()
        if return_value:
            result = session.get(MatchResult, UUID(return_value))

    return JobStatusResponse(
        job_id=job.id,
        status=job.get_status(),
        result=result,
        error=job.exc_info if job.is_failed else None,
    )
