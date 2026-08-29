from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Candidate(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Denormalized (not just reachable via job_description_id) so every
    # query — including the RQ worker, which has no live request/session to
    # derive tenant scope from — can filter by organization_id directly.
    organization_id: UUID = Field(foreign_key="organization.id", index=True)
    job_description_id: UUID = Field(foreign_key="jobdescription.id")
    # None until Stage 1 fills it from the resume, unless provided manually.
    name: Optional[str] = None
    email: Optional[str] = None
    resume_raw_text: str
    github_url: Optional[str] = None
    website_url: Optional[str] = None
    # Fields extracted from the resume in Stage 1, e.g. years_experience, skills, employment_history
    extracted_fields: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
