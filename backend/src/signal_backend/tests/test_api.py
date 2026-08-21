def test_create_job_description_and_candidate(client):
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
    stage2_result = verify_response.json()
    assert stage2_result["stage"] == 2
    assert stage2_result["evidence_confidence"] == "thin"

    detail_response = client.get(f"/candidates/{candidate_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["match_results"]) == 2
    assert {m["stage"] for m in detail["match_results"]} == {1, 2}


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
        candidate = Candidate(job_description_id=jd.id, name="No Stage1 Yet", resume_raw_text="...")
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        candidate_id = candidate.id

    response = client.post(f"/candidates/{candidate_id}/verify")
    assert response.status_code == 400


def test_shortlist_runs_stage2_for_multiple_candidates(client):
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
    results = shortlist_response.json()
    assert len(results) == 2
    assert all(r["stage"] == 2 for r in results)


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
