from signal_backend.models import Candidate, JobDescription
from signal_backend.pipeline.stage1.extract import run_stage1
from signal_backend.pipeline.stage1.parse_jd import parse_job_description


def test_parse_job_description(fake_llm_client):
    requirements = parse_job_description("We need a backend engineer.", llm_client=fake_llm_client)
    assert requirements[0]["category"] == "must_have"
    assert requirements[1]["source"] == "hiring_team_free_text"


def test_run_stage1(fake_llm_client):
    jd = JobDescription(title="Backend Engineer", raw_text="...", requirements=[{"text": "5+ years Python"}])
    candidate = Candidate(
        job_description_id=jd.id,
        name="Jane Doe",
        resume_raw_text="Jane Doe, 6 years as a Python engineer at Acme.",
    )

    match_result = run_stage1(candidate, jd, llm_client=fake_llm_client)

    assert candidate.extracted_fields["years_experience"] == 6
    assert match_result.fit_summary == "Strong match on core requirements."
    assert match_result.findings[0]["met"] == "yes"
