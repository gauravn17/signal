from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import BaseModel

from signal_backend.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """The app no longer auto-creates tables on startup (migrations are an
    explicit, separate step in real deployments) — so tests apply them once
    per session against the same local dev DB."""
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
from signal_backend.pipeline.stage1 import extract as stage1_extract
from signal_backend.pipeline.stage1 import parse_jd as stage1_parse_jd
from signal_backend.pipeline.stage2 import verify as stage2_verify
from signal_backend.services.github import GitHubClient


class FakeLLMClient:
    """Returns canned, schema-valid responses without hitting a real API."""

    def structured_complete(self, system: str, user: str, response_model: type[BaseModel]) -> BaseModel:
        if response_model is stage1_parse_jd.ParsedJD:
            return response_model.model_validate(
                {
                    "requirements": [
                        {"text": "5+ years Python", "category": "must_have", "source": "generic"},
                        {"text": "On-call experience", "category": "nice_to_have", "source": "hiring_team_free_text"},
                    ]
                }
            )
        if response_model is stage1_extract.Stage1Response:
            return response_model.model_validate(
                {
                    "contact_info": {
                        "name": "Extracted Name",
                        "email": "extracted@example.com",
                        "github_url": "https://github.com/extracted-user",
                        "website_url": "https://extracted.example.com",
                    },
                    "extracted_fields": {
                        "years_experience": 6,
                        "skills": ["Python", "FastAPI"],
                        "employment_history": [
                            {"company": "Acme", "title": "Engineer", "start_date": "2019", "end_date": "2025"}
                        ],
                        "education": ["BS Computer Science"],
                    },
                    "requirement_matches": [
                        {
                            "requirement_text": "5+ years Python",
                            "category": "must_have",
                            "met": "yes",
                            "evidence": "6 years at Acme as a Python engineer",
                        }
                    ],
                    "fit_summary": "Strong match on core requirements.",
                }
            )
        raise ValueError(f"FakeLLMClient has no canned response for {response_model}")

    def agentic_run(self, system, user, tools, tool_executor, response_model, max_steps=5):
        if response_model is stage2_verify.Stage2Response:
            return response_model.model_validate(
                {
                    "findings": [],
                    "disagreements": [],
                    "evidence_confidence": "thin",
                    "fit_summary": "No external evidence available; resume-only assessment.",
                }
            )
        raise ValueError(f"FakeLLMClient has no canned response for {response_model}")


@pytest.fixture
def fake_llm_client(monkeypatch):
    fake = FakeLLMClient()
    monkeypatch.setattr(stage1_parse_jd, "get_llm_client", lambda: fake)
    monkeypatch.setattr(stage1_extract, "get_llm_client", lambda: fake)
    monkeypatch.setattr(stage2_verify, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def fake_github_client(monkeypatch):
    fake = GitHubClient(
        http_client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    )
    monkeypatch.setattr(stage2_verify, "get_github_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def clear_stage2_queue():
    from signal_backend.services.queue import get_stage2_queue

    get_stage2_queue().empty()
    yield
    get_stage2_queue().empty()


@pytest.fixture
def run_queued_jobs():
    """Runs all currently-enqueued Stage 2 jobs synchronously, in-process
    (rq's SimpleWorker doesn't fork), so tests don't need a live worker."""

    def _run():
        from rq import SimpleWorker

        from signal_backend.services.queue import get_stage2_queue

        queue = get_stage2_queue()
        SimpleWorker([queue], connection=queue.connection).work(burst=True)

    return _run


@pytest.fixture
def client(fake_llm_client, fake_github_client):
    with TestClient(app) as c:
        yield c
