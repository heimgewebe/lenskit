import pytest
import asyncio
import httpx
from httpx import ASGITransport
from merger.lenskit.service.app import app, state, init_service
from merger.lenskit.service.models import JobRequest, Job

@pytest.fixture
def lifecycle_env(tmp_path):
    init_service(hub_path=tmp_path)
    return tmp_path

@pytest.mark.asyncio
async def test_stream_wakes_on_appended_logs(lifecycle_env):
    job_id = "test-wake"
    req = JobRequest(repos=[])
    job = Job.create(request=req)
    job.id = job_id
    state.job_store.add_job(job)

    lines_received = []

    async def run_stream():
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream("GET", f"/api/jobs/{job_id}/logs") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "end":
                            break
                        lines_received.append(data)

    stream_task = asyncio.create_task(run_stream())

    # Wait for stream to start and subscribe
    await asyncio.sleep(0.1)

    state.job_store.append_log_line(job_id, "hello world 1")
    await asyncio.sleep(0.1)

    state.job_store.append_log_line(job_id, "hello world 2")
    await asyncio.sleep(0.1)

    # End job
    job.status = "succeeded"
    state.job_store.update_job(job)

    await asyncio.wait_for(stream_task, timeout=2.0)

    assert lines_received == ["hello world 1", "hello world 2"]

@pytest.mark.asyncio
async def test_stream_ends_on_terminal_status(lifecycle_env):
    job_id = "test-term"
    req = JobRequest(repos=[])
    job = Job.create(request=req)
    job.id = job_id
    state.job_store.add_job(job)

    state.job_store.append_log_line(job_id, "start")

    lines_received = []

    async def run_stream():
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream("GET", f"/api/jobs/{job_id}/logs") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "end":
                            break
                        lines_received.append(data)

    stream_task = asyncio.create_task(run_stream())

    await asyncio.sleep(0.1)

    # Just update job status to failed.
    # We shouldn't hang.
    job.status = "failed"
    state.job_store.update_job(job)

    await asyncio.wait_for(stream_task, timeout=2.0)

    assert lines_received == ["start"]
    # Verify cleanup happened correctly
    assert job_id not in state.job_store._log_subscribers

@pytest.mark.asyncio
async def test_stream_exits_on_job_removal(lifecycle_env):
    job_id = "test-remove"
    req = JobRequest(repos=[])
    job = Job.create(request=req)
    job.id = job_id
    state.job_store.add_job(job)

    lines_received = []

    async def run_stream():
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream("GET", f"/api/jobs/{job_id}/logs") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "end":
                            break
                        lines_received.append(data)

    stream_task = asyncio.create_task(run_stream())

    await asyncio.sleep(0.1)
    assert job_id in state.job_store._log_subscribers

    # Remove job, should trigger exit of loop
    state.job_store.remove_job(job_id)

    await asyncio.wait_for(stream_task, timeout=2.0)

    assert len(lines_received) == 0
    # Subscriber cleanup verified
    assert job_id not in state.job_store._log_subscribers

@pytest.mark.asyncio
async def test_stream_idle_timeout_path(lifecycle_env, monkeypatch):
    job_id = "test-idle"
    req = JobRequest(repos=[])
    job = Job.create(request=req)
    job.id = job_id
    state.job_store.add_job(job)

    # Monkeypatch the wait_for timeout to a very small value to trigger it instantly
    import merger.lenskit.service.app
    original_wait_for = asyncio.wait_for

    async def mock_wait_for(aw, timeout):
        # Always timeout instantly if it's the event wait
        # We check by seeing if it's an Event.wait() coroutine, but a naive
        # approach is just replacing it for the module and passing a small timeout.
        return await original_wait_for(aw, timeout=0.01)

    monkeypatch.setattr(merger.lenskit.service.app.asyncio, "wait_for", mock_wait_for)

    lines_received = []

    async def run_stream():
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream("GET", f"/api/jobs/{job_id}/logs") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "end":
                            break
                        lines_received.append(data)

    stream_task = asyncio.create_task(run_stream())

    # Let it spin a bit through the mock timeouts
    await asyncio.sleep(0.1)

    # Send a log to ensure it's still alive and reacts
    state.job_store.append_log_line(job_id, "survived idle")
    await asyncio.sleep(0.1)

    job.status = "succeeded"
    state.job_store.update_job(job)

    await asyncio.wait_for(stream_task, timeout=2.0)

    assert lines_received == ["survived idle"]
