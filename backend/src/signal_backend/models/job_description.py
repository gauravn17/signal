from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class RequirementCategory(str, Enum):
    must_have = "must_have"
    nice_to_have = "nice_to_have"


class JobDescription(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    raw_text: str
    # Parsed structured requirements, each: {text, category, source: "generic" | "hiring_team_free_text"}
    requirements: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
