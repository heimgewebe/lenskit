

def test_explicit_reuse_policy(service_client):
    ctx = service_client

    # 1. Create initial job
    # We use a unique payload to ensure no collisions with other tests
    req_payload = {
        "repos": ["repo-test"],
        "level": "summary",
        "plan_only": True
    }

    resp1 = ctx.client.post("/api/jobs", json=req_payload, headers=ctx.headers)
    assert resp1.status_code == 200
    job1 = resp1.json()
    job1_id = job1["id"]

    # Simulate job completion to allow reuse
    # We access the store directly to update status
    job_obj = ctx.store.get_job(job1_id)
    assert job_obj is not None
    job_obj.status = "succeeded"
    ctx.store.update_job(job_obj)

    # 2. Create identical job (expect REUSE)
    resp2 = ctx.client.post("/api/jobs", json=req_payload, headers=ctx.headers)
    assert resp2.status_code == 200
    job2 = resp2.json()
    assert job2["id"] == job1_id

    # 3. Create identical job with force_new=True (expect NEW)
    req_payload_forced = req_payload.copy()
    req_payload_forced["force_new"] = True

    resp3 = ctx.client.post("/api/jobs", json=req_payload_forced, headers=ctx.headers)
    assert resp3.status_code == 200
    job3 = resp3.json()

    assert job3["id"] != job1_id

    # Verify job3 exists
    assert ctx.store.get_job(job3["id"]) is not None

def test_force_new_ignored_if_no_existing(service_client):
    ctx = service_client

    # Create job with force_new=True but no prior job exists
    req_payload = {
        "repos": ["repo-test"],
        "level": "max",
        "plan_only": True,
        "force_new": True
    }
    resp = ctx.client.post("/api/jobs", json=req_payload, headers=ctx.headers)
    assert resp.status_code == 200
    job = resp.json()

    assert ctx.store.get_job(job["id"]) is not None


def test_whitespace_only_include_paths_collapsed_to_none(service_client):
    """
    Ensure that whitespace-only paths (e.g. "   ") are treated consistently with ""
    and collapse the selection to None (All) under non-strict semantics.
    """
    ctx = service_client

    # Create job with an explicit empty string include path
    req_payload_empty = {
        "repos": ["repo-test"],
        "level": "summary",
        "plan_only": True,
        "include_paths_by_repo": {
            "repo-test": [""]
        }
    }
    resp1 = ctx.client.post("/api/jobs", json=req_payload_empty, headers=ctx.headers)
    assert resp1.status_code == 200
    job1_id = resp1.json()["id"]

    # Simulate completion
    job_obj = ctx.store.get_job(job1_id)
    job_obj.status = "succeeded"
    ctx.store.update_job(job_obj)

    # Create job with a whitespace-only include path
    req_payload_space = {
        "repos": ["repo-test"],
        "level": "summary",
        "plan_only": True,
        "include_paths_by_repo": {
            "repo-test": ["   "]
        }
    }
    resp2 = ctx.client.post("/api/jobs", json=req_payload_space, headers=ctx.headers)
    assert resp2.status_code == 200
    job2_id = resp2.json()["id"]

    # Should reuse the exact same job since both normalize to None
    assert job1_id == job2_id
