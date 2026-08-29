from uuid import uuid4

import pytest
from pydantic import ValidationError

from signal_backend.models import Candidate, EvidenceConfidence, JobDescription
from signal_backend.pipeline.stage1.extract import Stage1Response, _with_scheme, run_stage1
from signal_backend.pipeline.stage1.parse_jd import parse_job_description


class StaticLLMClient:
    """Returns one fixed, pre-validated Stage1Response regardless of prompt —
    lets each test control exactly what the model "said" without depending on
    the shared FakeLLMClient's one canned scenario."""

    def __init__(self, response: dict):
        self._response = response

    def structured_complete(self, system, user, response_model):
        return response_model.model_validate(self._response)


BASE_EXTRACTED_FIELDS = {
    "years_experience": None,
    "skills": [],
    "employment_history": [],
    "education": [],
}


def _requirement(req_id="req_001", req_type="experience", category="must_have", text="Some requirement"):
    return {"requirement_id": req_id, "requirement_type": req_type, "category": category, "text": text}


def _jd_and_candidate(requirements, resume_text="Some resume text."):
    org_id = uuid4()
    jd = JobDescription(organization_id=org_id, title="Role", raw_text="...", requirements=requirements)
    candidate = Candidate(
        organization_id=org_id, job_description_id=jd.id, name="Jane Doe", resume_raw_text=resume_text
    )
    return jd, candidate


def test_with_scheme_normalizes_bare_urls():
    assert _with_scheme("github.com/jane") == "https://github.com/jane"
    assert _with_scheme("https://github.com/jane") == "https://github.com/jane"
    assert _with_scheme("http://jane.dev") == "http://jane.dev"
    assert _with_scheme(None) is None


def test_parse_job_description_assigns_stable_ids_and_type(fake_llm_client):
    requirements = parse_job_description("We need a backend engineer.", llm_client=fake_llm_client)
    assert requirements[0]["requirement_id"] == "req_001"
    assert requirements[1]["requirement_id"] == "req_002"
    assert requirements[0]["category"] == "must_have"
    assert requirements[0]["requirement_type"] == "experience"
    assert requirements[1]["source"] == "hiring_team_free_text"


def test_run_stage1(fake_llm_client):
    jd, candidate = _jd_and_candidate([_requirement(text="5+ years Python")])
    candidate.resume_raw_text = "Jane Doe, 6 years as a Python engineer at Acme."

    match_result = run_stage1(candidate, jd, llm_client=fake_llm_client)

    assert candidate.extracted_fields["years_experience"] == 6
    assert match_result.fit_summary == "Strong match on core requirements."
    assert match_result.findings[0]["assessment"]["assessment"] == "strong"
    assert match_result.evidence_confidence == EvidenceConfidence.strong
    assert match_result.assessment_details["strengths"]
    assert candidate.name == "Jane Doe"  # manually-provided name wins over extraction


def test_run_stage1_fills_in_contact_info_when_not_provided(fake_llm_client):
    jd, candidate = _jd_and_candidate([_requirement(text="5+ years Python")])
    candidate.name = None
    candidate.resume_raw_text = "Extracted Name, 6 years as a Python engineer at Acme. github.com/extracted-user"

    run_stage1(candidate, jd, llm_client=fake_llm_client)

    assert candidate.name == "Extracted Name"
    assert candidate.email == "extracted@example.com"
    assert candidate.github_url == "https://github.com/extracted-user"
    assert candidate.website_url == "https://extracted.example.com"


def test_findings_carry_jd_owned_identity_not_model_output(fake_llm_client):
    """category/requirement_type/requirement_id come from the JD, never from
    the model — even though the fake client's canned response doesn't
    mention them, the persisted finding must have them correct."""
    jd, candidate = _jd_and_candidate(
        [_requirement(req_id="req_042", req_type="skill", category="nice_to_have", text="5+ years Python")]
    )

    match_result = run_stage1(candidate, jd, llm_client=fake_llm_client)

    finding = match_result.findings[0]
    assert finding["requirement_id"] == "req_042"
    assert finding["requirement_type"] == "skill"
    assert finding["category"] == "nice_to_have"
    assert finding["requirement_text"] == "5+ years Python"


@pytest.mark.parametrize(
    "req_type,assessment",
    [
        (
            "experience",
            {
                "kind": "experience",
                "assessment": "strong",
                "duration": "3 years",
                "context": "professional",
                "ownership": "owned the system end to end",
                "scale": "20M events/day",
                "evidence": [{"excerpt": "designed and operated a Kafka pipeline", "source": "resume"}],
                "gaps": [],
            },
        ),
        (
            "leadership",
            {
                "kind": "experience",
                "assessment": "moderate",
                "ownership": "led a team of 6 engineers",
                "evidence": [{"excerpt": "led a team of 6 engineers", "source": "resume"}],
                "gaps": ["duration of leadership role not stated"],
            },
        ),
        (
            "education",
            {
                "kind": "education",
                "assessment": "met",
                "degree_level": "Bachelor's",
                "field_of_study": "Computer Science",
                "evidence": [{"excerpt": "B.S. Computer Science", "source": "resume"}],
                "gaps": [],
            },
        ),
        (
            "certification",
            {
                "kind": "certification",
                "assessment": "not_met",
                "evidence": [],
                "gaps": ["no AWS certification mentioned in resume"],
            },
        ),
        (
            "other",
            {
                "kind": "other",
                "assessment": "unclear",
                "notes": "Resume doesn't state work authorization status",
                "evidence": [],
                "gaps": ["work authorization not stated"],
            },
        ),
    ],
)
def test_each_requirement_type_discriminated_variant_parses(req_type, assessment):
    """Structural test: each requirement_type's corresponding assessment
    shape validates through Stage1Response, not just experience/skill."""
    jd, candidate = _jd_and_candidate([_requirement(req_type=req_type)])
    llm_client = StaticLLMClient(
        {
            "contact_info": {},
            "extracted_fields": BASE_EXTRACTED_FIELDS,
            "requirement_assessments": [{"requirement_id": "req_001", "assessment": assessment}],
            "strengths": [],
            "gaps": [],
            "evidence_confidence": "moderate",
            "fit_summary": "ok",
        }
    )

    match_result = run_stage1(candidate, jd, llm_client=llm_client)

    assert match_result.findings[0]["assessment"]["kind"] == assessment["kind"]
    assert match_result.findings[0]["requirement_type"] == req_type


def test_old_schema_is_rejected():
    """Regression guard: the pre-redesign flat met:yes/partial/no shape must
    no longer validate — proves this isn't silently accepting stale data."""
    with pytest.raises(ValidationError):
        Stage1Response.model_validate(
            {
                "contact_info": {},
                "extracted_fields": BASE_EXTRACTED_FIELDS,
                "requirement_matches": [
                    {"requirement_text": "Python", "category": "must_have", "met": "yes", "evidence": "..."}
                ],
                "fit_summary": "ok",
            }
        )


def test_positional_mapping_ignores_mismatched_echoed_requirement_id():
    """The model's echoed requirement_id is a consistency check only — a
    mismatch must not change which JD requirement the assessment attaches to."""
    jd, candidate = _jd_and_candidate([_requirement(req_id="req_007", text="5+ years Python")])
    llm_client = StaticLLMClient(
        {
            "contact_info": {},
            "extracted_fields": BASE_EXTRACTED_FIELDS,
            "requirement_assessments": [
                {
                    "requirement_id": "req_999",  # deliberately wrong
                    "assessment": {"kind": "experience", "assessment": "strong", "evidence": [], "gaps": []},
                }
            ],
            "strengths": [],
            "gaps": [],
            "evidence_confidence": "thin",
            "fit_summary": "ok",
        }
    )

    match_result = run_stage1(candidate, jd, llm_client=llm_client)

    # Position 0's assessment still attaches to req_007 (the JD's actual
    # first requirement), not to whatever id the model echoed.
    assert match_result.findings[0]["requirement_id"] == "req_007"


def test_fewer_assessments_than_requirements_marks_missing_as_not_demonstrated():
    jd, candidate = _jd_and_candidate(
        [_requirement(req_id="req_001", text="Python"), _requirement(req_id="req_002", text="Kafka")]
    )
    llm_client = StaticLLMClient(
        {
            "contact_info": {},
            "extracted_fields": BASE_EXTRACTED_FIELDS,
            "requirement_assessments": [
                {
                    "requirement_id": "req_001",
                    "assessment": {"kind": "experience", "assessment": "strong", "evidence": [], "gaps": []},
                }
            ],
            "strengths": [],
            "gaps": [],
            "evidence_confidence": "thin",
            "fit_summary": "ok",
        }
    )

    match_result = run_stage1(candidate, jd, llm_client=llm_client)

    assert len(match_result.findings) == 2
    assert match_result.findings[1]["requirement_id"] == "req_002"
    assert match_result.findings[1]["assessment"]["assessment"] == "not_demonstrated"
