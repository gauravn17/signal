from uuid import uuid4

from signal_backend.models import Candidate, JobDescription
from signal_backend.pipeline.stage1.extract import _with_scheme, run_stage1
from signal_backend.pipeline.stage1.parse_jd import parse_job_description


def test_with_scheme_normalizes_bare_urls():
    assert _with_scheme("github.com/jane") == "https://github.com/jane"
    assert _with_scheme("https://github.com/jane") == "https://github.com/jane"
    assert _with_scheme("http://jane.dev") == "http://jane.dev"
    assert _with_scheme(None) is None


def test_parse_job_description(fake_llm_client):
    requirements = parse_job_description("We need a backend engineer.", llm_client=fake_llm_client)
    assert requirements[0]["category"] == "must_have"
    assert requirements[1]["source"] == "hiring_team_free_text"


def test_run_stage1(fake_llm_client):
    org_id = uuid4()
    jd = JobDescription(
        organization_id=org_id, title="Backend Engineer", raw_text="...", requirements=[{"text": "5+ years Python"}]
    )
    candidate = Candidate(
        organization_id=org_id,
        job_description_id=jd.id,
        name="Jane Doe",
        resume_raw_text="Jane Doe, 6 years as a Python engineer at Acme.",
    )

    match_result = run_stage1(candidate, jd, llm_client=fake_llm_client)

    assert candidate.extracted_fields["years_experience"] == 6
    assert match_result.fit_summary == "Strong match on core requirements."
    assert match_result.findings[0]["met"] == "yes"
    assert candidate.name == "Jane Doe"  # manually-provided name wins over extraction
    assert match_result.organization_id == org_id


def test_run_stage1_fills_in_contact_info_when_not_provided(fake_llm_client):
    org_id = uuid4()
    jd = JobDescription(
        organization_id=org_id, title="Backend Engineer", raw_text="...", requirements=[{"text": "5+ years Python"}]
    )
    candidate = Candidate(
        organization_id=org_id,
        job_description_id=jd.id,
        resume_raw_text="Extracted Name, 6 years as a Python engineer at Acme. github.com/extracted-user",
    )

    run_stage1(candidate, jd, llm_client=fake_llm_client)

    assert candidate.name == "Extracted Name"
    assert candidate.email == "extracted@example.com"
    assert candidate.github_url == "https://github.com/extracted-user"
    assert candidate.website_url == "https://extracted.example.com"
