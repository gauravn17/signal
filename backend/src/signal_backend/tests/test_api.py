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
