import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from signal_backend.main import app
from signal_backend.pipeline.stage1 import extract as stage1_extract
from signal_backend.pipeline.stage1 import parse_jd as stage1_parse_jd


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


@pytest.fixture
def fake_llm_client(monkeypatch):
    fake = FakeLLMClient()
    monkeypatch.setattr(stage1_parse_jd, "get_llm_client", lambda: fake)
    monkeypatch.setattr(stage1_extract, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def client(fake_llm_client):
    with TestClient(app) as c:
        yield c
