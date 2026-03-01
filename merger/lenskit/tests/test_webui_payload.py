import pytest
from playwright.sync_api import Page, Route
import json
import os
import time

UI_DIR = os.path.abspath("merger/lenskit/frontends/webui")

@pytest.fixture
def page_with_static(page: Page):
    # Log console
    page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))
    page.on("pageerror", lambda exc: print(f"PAGE ERROR: {exc}"))

    with open(os.path.join(UI_DIR, "index.html"), "r") as f:
        content = f.read()

    content = content.replace("__RLENS_ASSET_BASE__", "./")
    content = content.replace("__RLENS_BUILD__", "test-v1")

    page.route("http://localhost:8000/", lambda route: route.fulfill(
        status=200,
        body=content,
        content_type="text/html"
    ))

    def handle_static(route: Route):
        path = route.request.url.split("/")[-1].split("?")[0]
        file_path = os.path.join(UI_DIR, path)
        if os.path.exists(file_path):
            content_type = "text/plain"
            if path.endswith(".js"):
                content_type = "application/javascript"
            elif path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".html"):
                content_type = "text/html"

            with open(file_path, "rb") as f:
                route.fulfill(body=f.read(), content_type=content_type)
        else:
            route.continue_()

    page.route("**/app.js*", handle_static)
    page.route("**/materialize.js*", handle_static)
    page.route("**/style.css*", handle_static)

    page.route("**/api/version", lambda route: route.fulfill(json={"version": "test", "build_id": "test-1"}))
    page.route("**/api/health", lambda route: route.fulfill(json={"status": "ok", "hub": "/mock/hub", "merges_dir": "/mock/merges"}))
    page.route("**/api/artifacts", lambda route: route.fulfill(json=[]))
    page.route("**/api/repos*", lambda route: route.fulfill(json=["repoA", "repoB", "../dirtyRepo"]))

    return page

def test_run_merge_picks_up_pool_selections(page_with_static: Page):
    """
    Verifies that the 'Run Merge' button correctly picks up pool selections
    and uses Combined Job Mapping (strict_include_paths_by_repo) when partial selections exist.
    """
    pool_state = {
        "repoA": {"raw": None, "compressed": None}, # Full selection
        "repoB": {"raw": ["fileB.txt"], "compressed": ["fileB.txt"]} # Partial selection
    }

    page_with_static.add_init_script("window.__RLENS_TEST__ = true;")
    page_with_static.goto("http://localhost:8000/")

    page_with_static.evaluate(f"""
        const pool = {json.dumps(pool_state)};
        localStorage.setItem("lenskit.prescan.savedSelections.v1", JSON.stringify(pool));
    """)
    page_with_static.reload()
    page_with_static.wait_for_function("() => window.__rlens_pool_ready === true")
    page_with_static.wait_for_selector("#repoList input[name='repos']")

    # Select repoA and repoB
    page_with_static.evaluate("""
        const boxes = document.querySelectorAll('input[name="repos"]');
        boxes.forEach(b => {
            if (b.value === 'repoA' || b.value === 'repoB') b.checked = true;
        });
    """)

    payloads = []
    def handle_jobs(route: Route):
        if route.request.method == "POST":
            data = route.request.post_data_json or json.loads(route.request.post_data)
            payloads.append(data)
            route.fulfill(json={"id": "job-" + str(len(payloads)), "status": "queued"})
        else:
            route.continue_()

    page_with_static.route("**/api/jobs", handle_jobs)
    page_with_static.select_option("#mode", "gesamt")
    page_with_static.click("#jobForm button[type='submit']")

    def wait_for_payloads():
        start = time.time()
        while time.time() - start < 5:
            if len(payloads) == 1: return
            page_with_static.wait_for_timeout(50)
        raise TimeoutError(f"Payloads count {len(payloads)} != 1")

    wait_for_payloads()

    p = payloads[0]
    assert sorted(p["repos"]) == ["repoA", "repoB"]
    assert "include_paths_by_repo" in p
    ipbr = p["include_paths_by_repo"]
    assert ipbr["repoA"] is None # Full
    assert ipbr["repoB"] == ["fileB.txt"] # Partial
    assert p.get("strict_include_paths_by_repo") is True
    assert "include_paths" not in p or p["include_paths"] is None

    # Ensure global filters are cleared when pool is active (even partially)
    assert p.get("path_filter") is None
    assert p.get("extensions") is None


def test_run_merge_mixed_pool_and_non_pool(page_with_static: Page):
    """
    Verifies that if one repo is in the pool (partial) and another is NOT in the pool,
    the non-pool repo gets mapped to null (Full) in the combined job.
    """
    pool_state = {
        "repoA": {"raw": ["fileA.txt"], "compressed": ["fileA.txt"]}
        # repoB NOT in pool
    }

    page_with_static.add_init_script("window.__RLENS_TEST__ = true;")
    page_with_static.goto("http://localhost:8000/")

    page_with_static.evaluate(f"""
        const pool = {json.dumps(pool_state)};
        localStorage.setItem("lenskit.prescan.savedSelections.v1", JSON.stringify(pool));
    """)
    page_with_static.reload()
    page_with_static.wait_for_function("() => window.__rlens_pool_ready === true")
    page_with_static.wait_for_selector("#repoList input[name='repos']")

    page_with_static.evaluate("""
        const boxes = document.querySelectorAll('input[name="repos"]');
        boxes.forEach(b => {
            if (b.value === 'repoA' || b.value === 'repoB') b.checked = true;
        });
    """)

    payloads = []
    def handle_jobs(route: Route):
        if route.request.method == "POST":
            data = route.request.post_data_json or json.loads(route.request.post_data)
            payloads.append(data)
            route.fulfill(json={"id": "job-mixed", "status": "queued"})
        else:
            route.continue_()

    page_with_static.route("**/api/jobs", handle_jobs)
    page_with_static.select_option("#mode", "gesamt")
    page_with_static.click("#jobForm button[type='submit']")

    def wait_for_payloads():
        start = time.time()
        while time.time() - start < 5:
            if len(payloads) == 1: return
            page_with_static.wait_for_timeout(50)
        raise TimeoutError(f"Payloads count {len(payloads)} != 1")

    wait_for_payloads()

    p = payloads[0]
    assert sorted(p["repos"]) == ["repoA", "repoB"]
    assert p["include_paths_by_repo"]["repoA"] == ["fileA.txt"]
    assert p["include_paths_by_repo"]["repoB"] is None # Not in pool -> Full
    assert p.get("strict_include_paths_by_repo") is True


def test_run_merge_blocks_dirty_keys(page_with_static: Page):
    """
    Verifies that selecting a repo with a dirty name blocks submission.
    """
    page_with_static.add_init_script("window.__RLENS_TEST__ = true;")
    page_with_static.goto("http://localhost:8000/")
    page_with_static.wait_for_selector("#repoList input[name='repos']")

    # Select the dirty repo "../dirtyRepo"
    page_with_static.evaluate("""
        const boxes = document.querySelectorAll('input[name="repos"]');
        boxes.forEach(b => {
            if (b.value === '../dirtyRepo') b.checked = true;
        });
    """)

    payloads = []
    def handle_jobs(route: Route):
        if route.request.method == "POST":
            payloads.append(route.request.post_data)
            route.fulfill(json={})
        else:
            route.continue_()

    page_with_static.route("**/api/jobs", handle_jobs)

    # Handle alert
    dialog_message = []
    def handle_dialog(dialog):
        dialog_message.append(dialog.message)
        dialog.accept()
    page_with_static.on("dialog", handle_dialog)

    page_with_static.click("#jobForm button[type='submit']")

    # Wait a bit to ensure no network req happens
    page_with_static.wait_for_timeout(500)

    assert len(payloads) == 0
    assert len(dialog_message) > 0
    assert "Security: Invalid repository names detected" in dialog_message[0]

def test_run_merge_clears_global_filters_for_pool(page_with_static: Page):
    """
    Regression Test: If pool selection is active, global filters (path_filter, extensions)
    must be cleared to prevent silent dropping of explicitly selected files.
    """
    # 1. Setup Pool with explicit selection
    pool_state = {
        "repoA": {"raw": ["foo.txt"], "compressed": ["foo.txt"]}
    }
    page_with_static.add_init_script("window.__RLENS_TEST__ = true;")
    page_with_static.goto("http://localhost:8000/")

    page_with_static.evaluate(f"""
        const pool = {json.dumps(pool_state)};
        localStorage.setItem("lenskit.prescan.savedSelections.v1", JSON.stringify(pool));
    """)
    page_with_static.reload()
    page_with_static.wait_for_function("() => window.__rlens_pool_ready === true")

    # 2. Set global filters in UI (the trap)
    page_with_static.fill("#pathFilter", "src/")
    page_with_static.fill("#extFilter", ".js")

    # 3. Select Repo
    page_with_static.evaluate("""
        const boxes = document.querySelectorAll('input[name="repos"]');
        boxes.forEach(b => {
            if (b.value === 'repoA') b.checked = true;
        });
    """)

    # 4. Capture Payload
    payloads = []
    def handle_jobs(route: Route):
        if route.request.method == "POST":
            data = route.request.post_data_json or json.loads(route.request.post_data)
            payloads.append(data)
            route.fulfill(json={"id": "job-regr", "status": "queued"})
        else:
            route.continue_()

    page_with_static.route("**/api/jobs", handle_jobs)
    page_with_static.select_option("#mode", "gesamt")
    page_with_static.click("#jobForm button[type='submit']")

    # Wait for payload
    start = time.time()
    while len(payloads) == 0 and time.time() - start < 5:
        page_with_static.wait_for_timeout(50)

    assert len(payloads) == 1
    p = payloads[0]

    # 5. Assert Logic:
    # - Repo has include_paths_by_repo (pool active)
    # - path_filter and extensions MUST be null/None
    assert p["include_paths_by_repo"]["repoA"] == ["foo.txt"]
    assert p.get("path_filter") is None, "path_filter must be cleared when pool is active"
    assert p.get("extensions") is None, "extensions must be cleared when pool is active"
