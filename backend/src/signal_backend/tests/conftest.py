import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from signal_backend.main import app
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


@pytest.fixture
def client(fake_llm_client, fake_github_client):
    with TestClient(app) as c:
        yield c
