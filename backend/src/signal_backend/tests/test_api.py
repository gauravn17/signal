def test_stats_reflects_created_data(client):
    before = client.get("/stats").json()

    jd_response = client.post("/job-descriptions", json={"title": "Backend Engineer", "raw_text": "..."})
    jd_id = jd_response.json()["id"]
    client.post(
        "/candidates",
        data={"job_description_id": jd_id, "name": "Jane Doe"},
        files={"resume": ("resume.txt", b"Jane Doe resume.", "text/plain")},
    )

    after = client.get("/stats").json()
    assert after["job_description_count"] == before["job_description_count"] + 1
    assert after["candidate_count"] == before["candidate_count"] + 1


def test_list_job_descriptions(client):
    client.post("/job-descriptions", json={"title": "Backend Engineer", "raw_text": "..."})
    client.post("/job-descriptions", json={"title": "Frontend Engineer", "raw_text": "..."})

    response = client.get("/job-descriptions")
    assert response.status_code == 200
    titles = {jd["title"] for jd in response.json()}
    assert {"Backend Engineer", "Frontend Engineer"} <= titles


def test_create_candidate_without_manual_name_uses_extracted_contact_info(client):
    jd_response = client.post(
        "/job-descriptions",
        json={"title": "Backend Engineer", "raw_text": "We need a backend engineer with 5+ years Python."},
    )
    jd_id = jd_response.json()["id"]

    candidate_response = client.post(
        "/candidates",
        data={"job_description_id": jd_id},  # no name/email/github_url/website_url
        files={"resume": ("resume.txt", b"Extracted Name resume text.", "text/plain")},
    )
    assert candidate_response.status_code == 200
    candidate = candidate_response.json()["candidate"]
    assert candidate["name"] == "Extracted Name"
    assert candidate["email"] == "extracted@example.com"
    assert candidate["github_url"] == "https://github.com/extracted-user"


def test_create_job_description_and_candidate(client, run_queued_jobs):
    jd_response = client.post(
        "/job-descriptions",
        json={"title": "Backend Engineer", "raw_text": "We need a backend engineer with 5+ years Python."},
    )
    assert jd_response.status_code == 200
    jd = jd_response.json()
    assert jd["requirements"][0]["category"] == "must_have"

    candidate_response = client.post(
        "/candidates",
        data={"job_description_id": jd["id"], "name": "Jane Doe"},
        files={"resume": ("resume.txt", b"Jane Doe, 6 years as a Python engineer at Acme.", "text/plain")},
    )
    assert candidate_response.status_code == 200
    body = candidate_response.json()
    assert body["candidate"]["name"] == "Jane Doe"
    assert body["match_result"]["fit_summary"] == "Strong match on core requirements."

    list_response = client.get("/candidates", params={"job_description_id": jd["id"]})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    candidate_id = body["candidate"]["id"]

    verify_response = client.post(f"/candidates/{candidate_id}/verify")
    assert verify_response.status_code == 200
    job = verify_response.json()
    assert job["status"] in ("queued", "started", "finished")

    run_queued_jobs()

    status_response = client.get(f"/jobs/{job['job_id']}")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "finished"
    assert status["result"]["stage"] == 2
    assert status["result"]["evidence_confidence"] == "thin"

    detail_response = client.get(f"/candidates/{candidate_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["match_results"]) == 2
    assert {m["stage"] for m in detail["match_results"]} == {1, 2}


def test_job_status_404_for_unknown_job(client):
    response = client.get("/jobs/does-not-exist")
    assert response.status_code == 404


def test_verify_before_stage1_returns_400(client):
    from sqlmodel import Session

    from signal_backend.db.session import engine
    from signal_backend.models import Candidate, JobDescription

    jd_response = client.post(
        "/job-descriptions",
        json={"title": "Backend Engineer", "raw_text": "We need a backend engineer with 5+ years Python."},
    )
    jd_id = jd_response.json()["id"]

    with Session(engine, expire_on_commit=False) as session:
        jd = session.get(JobDescription, jd_id)
        candidate = Candidate(
            organization_id=jd.organization_id, job_description_id=jd.id, name="No Stage1 Yet", resume_raw_text="..."
        )
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        candidate_id = candidate.id

    response = client.post(f"/candidates/{candidate_id}/verify")
    assert response.status_code == 400


def test_shortlist_runs_stage2_for_multiple_candidates(client, run_queued_jobs):
    jd_response = client.post(
        "/job-descriptions",
        json={"title": "Backend Engineer", "raw_text": "We need a backend engineer with 5+ years Python."},
    )
    jd_id = jd_response.json()["id"]

    candidate_ids = []
    for name in ["Jane Doe", "John Smith"]:
        candidate_response = client.post(
            "/candidates",
            data={"job_description_id": jd_id, "name": name},
            files={"resume": ("resume.txt", f"{name} resume text.".encode(), "text/plain")},
        )
        candidate_ids.append(candidate_response.json()["candidate"]["id"])

    shortlist_response = client.post(f"/job-descriptions/{jd_id}/shortlist", json={"candidate_ids": candidate_ids})
    assert shortlist_response.status_code == 200
    jobs = shortlist_response.json()
    assert len(jobs) == 2

    run_queued_jobs()

    for job in jobs:
        status = client.get(f"/jobs/{job['job_id']}").json()
        assert status["status"] == "finished"
        assert status["result"]["stage"] == 2


def test_data_is_isolated_between_organizations(client):
    from sqlmodel import Session

    from signal_backend.db.session import engine
    from signal_backend.main import app
    from signal_backend.models import Organization, User, UserRole
    from signal_backend.services.auth import get_current_user

    jd_response = client.post("/job-descriptions", json={"title": "Confidential Role", "raw_text": "..."})
    jd_id = jd_response.json()["id"]
    candidate_response = client.post(
        "/candidates",
        data={"job_description_id": jd_id, "name": "Jane Doe"},
        files={"resume": ("resume.txt", b"Jane Doe resume text.", "text/plain")},
    )
    candidate_id = candidate_response.json()["candidate"]["id"]

    from uuid import uuid4

    unique = uuid4()
    with Session(engine, expire_on_commit=False) as session:
        other_org = Organization(name="Other Org")
        session.add(other_org)
        session.commit()
        session.refresh(other_org)
        other_user = User(
            organization_id=other_org.id,
            email=f"other-{unique}@example.com",
            role=UserRole.admin,
            external_auth_id=f"other-external-id-{unique}",
        )
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

    app.dependency_overrides[get_current_user] = lambda: other_user

    assert client.get(f"/job-descriptions/{jd_id}").status_code == 404
    assert client.get(f"/candidates/{candidate_id}").status_code == 404
    assert candidate_id not in [c["id"] for c in client.get("/candidates", params={"job_description_id": jd_id}).json()]
    assert "Confidential Role" not in {jd["title"] for jd in client.get("/job-descriptions").json()}
    assert client.get("/stats").json()["job_description_count"] == 0


def test_shortlist_rejects_candidate_from_other_jd(client):
    jd1_response = client.post("/job-descriptions", json={"title": "Backend Engineer", "raw_text": "..."})
    jd2_response = client.post("/job-descriptions", json={"title": "Frontend Engineer", "raw_text": "..."})
    jd1_id = jd1_response.json()["id"]
    jd2_id = jd2_response.json()["id"]

    candidate_response = client.post(
        "/candidates",
        data={"job_description_id": jd1_id, "name": "Jane Doe"},
        files={"resume": ("resume.txt", b"Jane Doe resume text.", "text/plain")},
    )
    candidate_id = candidate_response.json()["candidate"]["id"]

    response = client.post(f"/job-descriptions/{jd2_id}/shortlist", json={"candidate_ids": [candidate_id]})
    assert response.status_code == 400
