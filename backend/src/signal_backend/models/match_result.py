from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class PipelineStage(int, Enum):
    stage1_bulk = 1
    stage2_verification = 2


class EvidenceConfidence(str, Enum):
    thin = "thin"  # resume-only, no corroborating sources
    moderate = "moderate"  # partial corroboration
    strong = "strong"  # multiple sources agree


class MatchResult(SQLModel, table=True):
    """
    Output of a pipeline stage for a single candidate against a JD.

    Fit and evidence_confidence are deliberately separate fields (not combined
    into one score) per the project's no-black-box-score design principle.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organization.id", index=True)
    candidate_id: UUID = Field(foreign_key="candidate.id")
    job_description_id: UUID = Field(foreign_key="jobdescription.id")
    stage: PipelineStage

    # Human-readable reasoning, not a numeric score.
    fit_summary: str = ""
    evidence_confidence: Optional[EvidenceConfidence] = None

    # Stage 1: per-requirement match notes. Stage 2: cross-referenced findings,
    # each noting which source(s) support/contradict a claim.
    findings: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    # Explicit disagreements between sources (e.g. resume vs. GitHub timeline).
    disagreements: list[dict] = Field(default_factory=list, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
