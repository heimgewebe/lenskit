import asyncio
import time
import httpx
from merger.lenskit.service.app import app, state, init_service
from merger.lenskit.service.models import JobRequest, Job
import pathlib
from httpx import ASGITransport

async def test_sse_polling_overhead():
    # Setup test env
    hub_path = pathlib.Path("./benchmark_hub").resolve()
    hub_path.mkdir(exist_ok=True)
    init_service(hub_path=hub_path)

    job_id = "bench-job-1"
    req = JobRequest(repos=["repo-test"])

    job = Job.create(request=req)
    job.id = job_id
    state.job_store.add_job(job)

    async def simulate_job_activity():
        # Slow down job updates to trigger the busy sleep polling
        for i in range(10):
            await asyncio.sleep(0.5)
            state.job_store.append_log_line(job_id, f"Line {i}")
            current_job = state.job_store.get_job(job_id)
            state.job_store.update_job(current_job)

        job.status = "succeeded"
        state.job_store.update_job(job)

    async def stream_logs(client_id):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            t0 = time.time()
            line_count = 0
            # start streaming logs
            async with client.stream("GET", f"/api/jobs/{job_id}/logs") as response:
                async for line in response.aiter_lines():
                    if line:
                        line_count += 1

            t1 = time.time()
            return t1 - t0, line_count

    print("Running concurrent stream benchmark (100 streams)...")
    t0 = time.time()

    t_job = asyncio.create_task(simulate_job_activity())

    # Run 100 concurrent streams to amplify CPU usage of the polling loop
    tasks = []
    for i in range(100):
        tasks.append(stream_logs(i))

    results = await asyncio.gather(*tasks)
    await t_job

    t1 = time.time()
    avg_dur = sum([r[0] for r in results]) / len(results)

    # Actually what we want to measure is overhead.
    # The true measure of polling inefficiency is that each client polls `await asyncio.sleep(SSE_POLL_SEC)`
    # instead of waking up on an event. With `asyncio.sleep`, 100 clients wake up 4 times a second (0.25s),
    # doing disk I/O each time (run_in_threadpool -> read_log_chunk).
    # That is 400 disk accesses/second!
    print(f"Total time taken: {t1 - t0:.3f} seconds. Average duration: {avg_dur:.3f}")

if __name__ == "__main__":
    asyncio.run(test_sse_polling_overhead())
