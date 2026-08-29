from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Organization(SQLModel, table=True):
    """A tenant. github_token/llm_api_key are BYOK — encrypted at rest via
    services/crypto.py — so one org's GitHub rate limit / LLM usage/billing
    never affects another's."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    github_token_encrypted: Optional[str] = None
    llm_api_key_encrypted: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
