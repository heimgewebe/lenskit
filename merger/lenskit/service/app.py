from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import os
import asyncio
import json
import time
import ipaddress
import logging
import re
from datetime import datetime, timezone

from .models import JobRequest, Job, Artifact, AtlasRequest, AtlasArtifact, AtlasEffective, calculate_job_hash, PrescanRequest, PrescanResponse, FSRoot, FSRootsResponse
from .jobstore import JobStore
from .runner import JobRunner
from .logging_provider import LogProvider, FileLogProvider
from .auth import verify_token
from ..adapters.security import (
    get_security_config,
    validate_hub_path,
    validate_repo_name,
    InvalidPathError,
    AccessDeniedError,
)
from ..adapters.filesystem import resolve_fs_path, list_allowed_roots, issue_fs_token
from ..adapters.atlas import AtlasScanner, render_atlas_md
from ..adapters.metarepo import sync_from_metarepo
from ..adapters import sources as sources_refresh
from ..adapters import diagnostics as diagnostics_rebuild

try:
    from ..core.merge import get_merges_dir, SPEC_VERSION, prescan_repo
except ImportError:
    from merger.lenskit.core.merge import get_merges_dir, SPEC_VERSION, prescan_repo

# Global Version Info
SERVER_START_TIME = datetime.now(timezone.utc).isoformat()

def _get_server_version():
    # 1. Env Var (Canonical for builds)
    env_ver = os.getenv("RLENS_VERSION")
    if env_ver:
        return env_ver

    # 2. Git Hash
    try:
        import subprocess
        # Robustly find git root
        cwd_candidate = Path(__file__).parent
        try:
            repo_root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(cwd_candidate),
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            repo_root = str(cwd_candidate)

        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass

    return "dev"

SERVER_VERSION = _get_server_version()

# Build ID for cache busting
# If RLENS_BUILD_ID is set (CI/CD), use it (stable per build).
# Else fall back to SERVER_VERSION (if git hash).
# If dev/unknown, append timestamp to force reload on restarts.
_env_build_id = os.getenv("RLENS_BUILD_ID")
if _env_build_id:
    BUILD_ID = _env_build_id
elif SERVER_VERSION != "dev":
    BUILD_ID = SERVER_VERSION
else:
    BUILD_ID = f"dev-{int(time.time())}"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="rLens", version=SERVER_VERSION)

@app.exception_handler(InvalidPathError)
async def invalid_path_handler(request: Request, exc: InvalidPathError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(AccessDeniedError)
async def access_denied_handler(request: Request, exc: AccessDeniedError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})

# GC Configuration
GC_MAX_JOBS = int(os.getenv("RLENS_GC_MAX_JOBS", "100"))
GC_MAX_AGE_HOURS = int(os.getenv("RLENS_GC_MAX_AGE_HOURS", "24"))
# SSE polling (seconds)
SSE_POLL_SEC = float(os.getenv("RLENS_SSE_POLL_SEC", "0.25"))

# Security: Root Jail for File System Browsing
# Set to system root to allow full access, but preventing traversal above it (which is impossible anyway).
# Can be overridden if needed via Env or Config in future.
FS_ROOT = Path("/").resolve()

def _is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except Exception:
        return False

# Cache-Control Middleware to support aggressive busting for WebUI
# This is critical for preventing browsers (Brave/Chrome) from serving stale UI
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)

    # Target specific UI assets and the root index
    # Note: request.url.path includes the leading slash
    path = request.url.path
    if path in ["/", "/index.html", "/app.js", "/style.css"]:
        # "no-store" is the strongest directive.
        # "must-revalidate" is implied by no-store in modern browsers, but harmless.
        # We simplify to no-store but keep Pragma/Expires for legacy/proxy robustness.
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response

# Global State
class ServiceState:
    hub: Path = None
    merges_dir: Path = None
    job_store: JobStore = None
    runner: JobRunner = None
    log_provider: LogProvider = None

state = ServiceState()

def init_service(hub_path: Path, token: Optional[str] = None, host: str = "127.0.0.1", merges_dir: Optional[Path] = None):
    state.hub = hub_path
    state.merges_dir = merges_dir
    state.job_store = JobStore(hub_path)
    state.runner = JobRunner(state.job_store)
    state.log_provider = FileLogProvider(state.job_store)

    # Configure Security
    sec = get_security_config()
    sec.set_token(token)
    # Allowlist the Hub
    sec.add_allowlist_root(hub_path)
    # Allowlist Merges Dir if separate
    if merges_dir:
        sec.add_allowlist_root(merges_dir)

    # Allow System Root (Home) for Atlas
    # "System" root maps to user home (e.g. /home/alex), not /
    try:
        sec.add_allowlist_root(Path.home().resolve())
    except Exception as e:
        logger.debug("Could not allow system root: %s", e, exc_info=True)

    # DANGEROUS CAPABILITY:
    # Allows rLens to browse the entire filesystem ("/") via API.
    # Must be explicitly enabled.
    if os.getenv("RLENS_ALLOW_FS_ROOT", "0") == "1":
        sec.add_allowlist_root(Path("/"))

    # Apply CORS based on host
    # Prevent middleware duplication (if init called multiple times in tests)
    has_cors = any(m.cls == CORSMiddleware for m in app.user_middleware)
    if not has_cors:
        if _is_loopback_host(host):
            # Regex for localhost/127.0.0.1 with any port
            allow_origin_regex = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
            allow_origins = []
        else:
            allow_origin_regex = None
            allow_origins = [] # Strict for non-loopback by default

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "x-rlens-token"],
        )

def _list_dir(candidate: Path) -> Dict[str, Any]:
    # Defense-in-depth: always re-validate before touching the filesystem.
    sec = get_security_config()
    resolved = sec.validate_path(candidate)

    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    dirs: List[str] = []
    files: List[str] = []
    entries: List[Dict[str, Any]] = []

    try:
        for child in sorted(resolved.iterdir(), key=lambda x: x.name.lower()):
            if child.is_dir():
                dirs.append(child.name)
                entries.append({"name": child.name, "type": "dir", "token": issue_fs_token(child.resolve())})
            else:
                files.append(child.name)
                entries.append({"name": child.name, "type": "file"})
    except OSError as e:
        logger.error(f"Error listing {resolved}: {e}")
        raise HTTPException(status_code=500, detail="Error listing directory")

    return {"abs": str(resolved), "dirs": dirs, "files": files, "entries": entries}

@app.get("/api/fs/roots", response_model=FSRootsResponse, dependencies=[Depends(verify_token)])
def api_fs_roots():
    """
    Return a stable list of allowed roots for the picker & agents.
    The client should prefer token navigation.
    """
    roots = list_allowed_roots(state.hub, getattr(state, "merges_dir", None))
    # Add tokens for each root
    out = []
    for r in roots:
        p = Path(r["path"]).resolve()
        out.append(FSRoot(
            id=r["id"],
            path=str(p), # Ensure reported path matches token path exactly
            token=issue_fs_token(p)
        ))
    return FSRootsResponse(roots=out)

@app.get("/api/fs", dependencies=[Depends(verify_token)])
@app.get("/api/fs/list", dependencies=[Depends(verify_token)])
def api_fs_list(token: Optional[str] = None, root: Optional[str] = None, rel: Optional[str] = None):
    """
    FS listing endpoint.
    Canonical: ?token=<opaque>
    Transitional: ?root=<root_id>&rel=   (base only; subpaths require tokens)
    """
    hub = state.hub
    merges_dir = getattr(state, "merges_dir", None)
    trusted = resolve_fs_path(hub=hub, merges_dir=merges_dir, root_id=root, rel_path=rel, token=token)
    payload = _list_dir(trusted.path)
    # Add parent token for upward navigation if possible
    try:
        # Only offer parent if parent itself is allowed (avoid broken Up + reduce taint)
        sec = get_security_config()
        p = trusted.path
        if p.parent and p.parent != p:
            parent_resolved = sec.validate_path(p.parent)
            payload["parent_token"] = issue_fs_token(parent_resolved)
    except Exception:
        pass
    return {"root": root, "rel": rel, "token": token, **payload}

@app.post("/api/sources/refresh", dependencies=[Depends(verify_token)])
def api_sources_refresh():
    if not state.hub:
        raise HTTPException(status_code=400, detail="Hub not configured")
    try:
        return sources_refresh.refresh(state.hub)
    except Exception:
        logger.exception("Sources refresh failed")
        raise HTTPException(status_code=500, detail="Sources refresh failed")

@app.post("/api/diagnostics/rebuild", dependencies=[Depends(verify_token)])
def api_diagnostics_rebuild():
    if not state.hub:
        raise HTTPException(status_code=400, detail="Hub not configured")
    try:
        return diagnostics_rebuild.rebuild(state.hub)
    except Exception:
        logger.exception("Diagnostics rebuild failed")
        raise HTTPException(status_code=500, detail="Diagnostics rebuild failed")

@app.post("/api/extras/refresh_all", dependencies=[Depends(verify_token)])
def api_extras_refresh_all(payload: Dict[str, Any] = Body(default_factory=dict)):
    """
    Orchestrates optional metarepo-sync + sources refresh + diagnostics rebuild.

    SAFE DEFAULTS:
      - no sync unless explicitly requested
      - apply-sync only if payload.sync.mode == "apply"

    Example:
      { "sync": { "mode": "dry_run" } }
      { "sync": { "mode": "apply" } }
    """
    if not state.hub:
        raise HTTPException(status_code=400, detail="Hub not configured")

    # Sync only if explicitly requested with a valid mode.
    # This prevents accidental sync runs from payloads like { "sync": {} }.
    sync_cfg = payload.get("sync")
    sync_mode = None
    should_sync = False
    if isinstance(sync_cfg, dict):
        m = sync_cfg.get("mode")
        if m in ("dry_run", "apply"):
            sync_mode = m
            should_sync = True

    result = {
        "status": "ok",
        "sync": {"skipped": True},
        "refresh": {},
        "diagnostics": {}
    }

    # 1. Optional Sync
    if should_sync:
        try:
            # We assume "dry_run" is NOT what we want for a "refresh" button, we want "apply".
            # Or should we default to dry_run? User says "refresh_all... optionaler sync...".
            # Usually "refresh" implies getting latest state.
            # But sync_from_metarepo modifies disk (Manifest -> Fleet).
            # Let s assume "apply" is desired if sync=True.
            # Also target list? Default to all? None = all.
            mode = "apply" if sync_mode == "apply" else "dry_run"
            sync_report = sync_from_metarepo(hub_path=state.hub, mode=mode, targets=None)

            if sync_report.get("status") != "ok":
                # Hard fail as requested
                # Warning: msg might contain sensitive details if generated by sync logic
                # However, usually "message" is user-facing. We'll trust sync report message for now,
                # or sanitize it if unsure. Let's use a generic error for safety.
                logger.error(f"Sync failed in refresh_all: {sync_report}")
                raise HTTPException(status_code=500, detail="Sync failed")

            result["sync"] = sync_report
        except HTTPException:
            raise
        except Exception:
            logger.exception("Sync failed during refresh_all")
            raise HTTPException(status_code=500, detail="Sync failed")

    # 2. Sources Refresh
    try:
        refresh_res = sources_refresh.refresh(state.hub)
        result["refresh"] = refresh_res
    except Exception:
        logger.exception("Sources refresh failed during refresh_all")
        raise HTTPException(status_code=500, detail="Sources refresh failed")

    # 3. Diagnostics Rebuild
    try:
        diag_res = diagnostics_rebuild.rebuild(state.hub)
        result["diagnostics"] = diag_res
    except Exception:
        logger.exception("Diagnostics rebuild failed during refresh_all")
        raise HTTPException(status_code=500, detail="Diagnostics rebuild failed")

    return result

@app.get("/api/version")
def api_version():
    return {
        "version": SERVER_VERSION,
        "build_id": BUILD_ID,
        "started_at": SERVER_START_TIME
    }

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": SPEC_VERSION,
        "server_version": SERVER_VERSION,
        "hub": str(state.hub),
        "merges_dir": str(state.merges_dir) if state.merges_dir else None,
        "auth_enabled": bool(get_security_config().token),
        "running_jobs": len(state.runner.futures) if state.runner else 0
    }

@app.get("/api/repos", dependencies=[Depends(verify_token)])
def list_repos(hub: Optional[str] = None):
    # If hub provided, validate it first
    target_hub = state.hub
    if hub:
        target_hub = validate_hub_path(hub)

    # Use runner's helper or core helper
    from .runner import _find_repos
    return _find_repos(target_hub)

@app.post("/api/prescan", response_model=PrescanResponse, dependencies=[Depends(verify_token)])
def api_prescan(request: PrescanRequest):
    if not state.hub:
        raise HTTPException(status_code=400, detail="Hub not configured")

    # Resolve repo
    repo_name = validate_repo_name(request.repo)
    repo_root = state.hub / repo_name
    if not repo_root.exists() or not repo_root.is_dir():
        raise HTTPException(status_code=404, detail=f"Repo {repo_name} not found")

    try:
        # Run prescan
        result = prescan_repo(
            repo_root=repo_root,
            max_depth=request.max_depth,
            ignore_globs=request.ignore_globs
        )
        # Convert to response
        return PrescanResponse(
            root=result["root"],
            tree=result["tree"],
            signature=result["signature"],
            file_count=result["file_count"],
            total_bytes=result["total_bytes"]
        )
    except Exception as e:
        logger.exception(f"Prescan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs", response_model=Job, dependencies=[Depends(verify_token)])
def create_job(request: JobRequest):
    # Validate Hub in request
    req_hub = state.hub
    if request.hub:
         req_hub = validate_hub_path(request.hub)

    # Apply default merges dir if not specified
    if not request.merges_dir and state.merges_dir:
        request.merges_dir = str(state.merges_dir)

    # Validate repo names early (API must be strict)
    if request.repos:
        request.repos = [validate_repo_name(r) for r in request.repos]

    # Validate strict_include_paths_by_repo (Sync Check for 400)
    if request.strict_include_paths_by_repo and request.include_paths_by_repo:
        if not request.repos:
             # Implicit all repos? If so, we can't easily validate keys without listing dir.
             # But usually strict mode is used with explicit repos.
             pass
        else:
            missing = [r for r in request.repos if r not in request.include_paths_by_repo]
            if missing:
                raise HTTPException(status_code=400, detail=f"Strict Mode Violation: include_paths_by_repo missing keys for: {missing}")

    # --- Idempotency & GC ---
    resolved_hub_str = str(req_hub)
    content_hash = calculate_job_hash(request, resolved_hub_str, SPEC_VERSION)

    # Lazy GC
    state.job_store.cleanup_jobs(max_jobs=GC_MAX_JOBS, max_age_hours=GC_MAX_AGE_HOURS)

    existing = state.job_store.find_job_by_hash(content_hash)
    if existing and not request.force_new:
        # Check if we should reuse
        if existing.status in ("queued", "running", "canceling"):
             logger.info(f"Reusing existing active job {existing.id}")
             return existing

        # Policy: Reuse succeeded jobs (server-side default: yes)
        if existing.status == "succeeded":
             logger.info(f"Reusing existing succeeded job {existing.id}")
             return existing

    job = Job.create(request, content_hash=content_hash)
    job.hub_resolved = resolved_hub_str
    state.job_store.add_job(job)
    state.runner.submit_job(job.id)
    return job

@app.get("/api/jobs", response_model=List[Job], dependencies=[Depends(verify_token)])
def get_jobs(status: Optional[str] = None, limit: int = 20):
    jobs = state.job_store.get_all_jobs()
    if status:
        jobs = [j for j in jobs if j.status == status]
    return jobs[:limit]

@app.get("/api/jobs/{job_id}", response_model=Job, dependencies=[Depends(verify_token)])
def get_job(job_id: str):
    job = state.job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(verify_token)])
def cancel_job(job_id: str):
    job = state.job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["succeeded", "failed", "canceled"]:
        return {"status": job.status, "message": "Job already finished"}

    if job.status in ["queued", "running"]:
        job.status = "canceling"
        state.job_store.update_job(job)
    return {"status": job.status}

@app.get("/api/jobs/{job_id}/logs", dependencies=[Depends(verify_token)], response_model=None)
async def stream_logs(request: Request, job_id: str, last_id: Optional[int] = Query(None)):
    # SSE Stream
    job = state.job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Determine start index
    # Prioritize Last-Event-ID header if present
    start_idx = 0
    if request.headers.get("Last-Event-ID"):
        try:
            # Last-Event-ID is a 1-based line id; negative values are clamped defensively
            start_idx = max(0, int(request.headers.get("Last-Event-ID")))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID")
    elif last_id is not None:
        start_idx = max(0, last_id)

    async def log_generator():
        # last_idx here represents 'last_line_id' (1-based index)
        # 0 means "nothing sent yet"
        last_idx = start_idx
        while True:
            # Stop work if client disconnected (prevents zombie generators)
            try:
                if await request.is_disconnected():
                    break
            except Exception:
                pass

            # Read logs from file (async safe)
            # Use abstracted provider to allow deterministic mocking in tests
            # Optimized: read chunks using line skip (O(1) memory, preserves line-based semantics)
            chunk_data = await run_in_threadpool(state.log_provider.read_log_chunk, job_id, last_idx)

            if chunk_data:
                for line, new_id in chunk_data:
                    yield f"id: {new_id}\ndata: {line}\n\n"
                    last_idx = new_id

            # Check status for completion
            current_job = await run_in_threadpool(state.job_store.get_job, job_id)
            if not current_job:
                break

            if current_job.status in ["succeeded", "failed", "canceled"]:
                # Ensure we sent everything
                chunk_data = await run_in_threadpool(state.log_provider.read_log_chunk, job_id, last_idx)
                if chunk_data:
                    for line, new_id in chunk_data:
                        yield f"id: {new_id}\ndata: {line}\n\n"
                        last_idx = new_id

                yield "event: end\ndata: end\n\n"
                break

            # Throttle polling (avoid busy-loop CPU burn)
            await asyncio.sleep(SSE_POLL_SEC)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/artifacts", response_model=List[Artifact], dependencies=[Depends(verify_token)])
def list_artifacts(repo: Optional[str] = None):
    arts = state.job_store.get_all_artifacts()
    if repo:
        arts = [a for a in arts if repo in a.repos]
    return arts

@app.get("/api/artifacts/latest", dependencies=[Depends(verify_token)])
def get_latest_artifact(repo: str, level: str = "max", mode: str = "gesamt"):
    # "Heimgewebe-Hebel" - Return the single latest matching artifact
    arts = state.job_store.get_all_artifacts()
    matches = []

    for a in arts:
        # Filter by params
        if a.params.level != level:
            continue
        if a.params.mode != mode:
            continue

        # Filter by repo
        # If artifact covers specific repos, 'repo' must be in that list.
        # If artifact covers all (empty list/None), it counts as a match for any repo query?
        # Or does 'latest?repo=X' imply "Snapshot of X"?
        # Usually "Snapshot of X" means X is in the list.
        if a.repos:
            if repo in a.repos:
                matches.append(a)
        else:
            # Artifact is for ALL repos.
            # Does this count as "latest artifact for repo X"?
            # Yes, if X is in the hub. We assume it is.
            matches.append(a)

    if not matches:
        raise HTTPException(status_code=404, detail="No matching artifact found")

    # Sort by created_at desc (lexicographical ISO string sort works)
    # The JobStore already returns sorted list (desc), but to be safe/explicit:
    latest = max(matches, key=lambda x: x.created_at)
    return latest

@app.get("/api/artifacts/{id}", dependencies=[Depends(verify_token)])
def get_artifact(id: str):
    art = state.job_store.get_artifact(id)
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return art

def _serve_file(base_dir: Path, requested_path: Union[str, Path], filename: Optional[str] = None) -> FileResponse:
    """
    Unified file serving logic with security checks.
    1. Validates base_dir against security allowlist.
    2. Derives file_path from base_dir + requested_path.
    3. Ensures file_path is within base_dir.
    4. Returns a FileResponse.
    """
    # 1. Early Traversal & Absolute Path Guard (UX/400)
    req_p = Path(requested_path)
    # Stricter segment check to allow filenames like "foo..bar.md" while blocking traversal
    if req_p.is_absolute() or any(part == ".." for part in req_p.parts) or "\\" in str(req_p):
        raise HTTPException(status_code=400, detail="Invalid path: Traversal, absolute paths, or backslashes not allowed")

    sec = get_security_config()
    try:
        # 2. Validate Base (returns canonical path)
        resolved_base = sec.validate_path(base_dir)

        # 3. Derive File Path
        # Joining with Path(requested_path) is now safe because we checked is_absolute()
        target_path = resolved_base / req_p

        # 4. Validate Target
        # validate_path returns resolved/canonical paths.
        resolved_file = sec.validate_path(target_path)

        # 5. Consistency: Explicitly check if file is inside the intended validated base_dir
        resolved_file.relative_to(resolved_base)

        if not resolved_file.exists():
            raise HTTPException(status_code=404, detail="File on disk missing")

        if not resolved_file.is_file():
            raise HTTPException(status_code=404, detail="File on disk missing")

        return FileResponse(resolved_file, filename=filename or resolved_file.name)
    except AccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidPathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: File outside of expected directory")


@app.get("/api/artifacts/{id}/download", dependencies=[Depends(verify_token)])
def download_artifact(id: str, key: str = "md"):
    art = state.job_store.get_artifact(id)
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")

    filename = art.paths.get(key)
    if not filename:
        # Try finding part
        if key == "md" and "canonical_md" in art.paths:
            filename = art.paths["canonical_md"]
        elif key == "json" and "index_json" in art.paths:
             filename = art.paths["index_json"]
        else:
             raise HTTPException(status_code=404, detail=f"File key '{key}' not found in artifact")

    # Determine base directory
    # Priority 1: Effective merges_dir captured at creation time (new field)
    if art.merges_dir:
        p = Path(art.merges_dir)
        if not p.is_absolute():
            # Resolve relative paths against HUB (defense in depth for drifted persistence)
            merges_dir = (Path(art.hub) / p)
        else:
            merges_dir = p
    # Priority 2: Requested merges_dir (params)
    # Backward compatibility: if art.merges_dir is None (legacy artifacts)
    elif art.params.merges_dir:
        p = Path(art.params.merges_dir)
        if not p.is_absolute():
            merges_dir = (Path(art.hub) / p)
        else:
            merges_dir = p
    else:
        # Default: hub/merges
        merges_dir = get_merges_dir(Path(art.hub))

    # Unified file serving with security checks
    return _serve_file(merges_dir, filename, filename=filename)

# Atlas API

@app.post("/api/atlas", response_model=AtlasArtifact, dependencies=[Depends(verify_token)])
async def create_atlas(request: AtlasRequest, background_tasks: BackgroundTasks):
    # Determine root to scan
    hub = state.hub
    if not hub:
        raise HTTPException(status_code=400, detail="Hub not configured")

    # Defaults for effective params
    effective_max_depth = request.max_depth
    effective_max_entries = request.max_entries
    effective_excludes = (request.exclude_globs or []).copy()

    # Resolve scan root
    try:
        # Canonical: token-based root selection (no user path expressions)
        if request.root_token:
            trusted = resolve_fs_path(
                hub=hub,
                merges_dir=state.merges_dir,
                token=request.root_token,
            )
            scan_root = trusted.path
        else:
            # Transitional: root_id only (known ids)
            # STRICT: No silent fallback to "hub". User must be explicit.
            if not request.root_id:
                raise HTTPException(status_code=400, detail="Missing root directory (provide root_token or root_id)")

            root_id = request.root_id
            if root_id not in ("hub", "merges", "system"):
                # Strict rejection of raw paths for Atlas to satisfy CodeQL
                raise HTTPException(status_code=400, detail="Invalid root directory identifier")

            trusted = resolve_fs_path(
                hub=hub,
                merges_dir=state.merges_dir,
                root_id=root_id,
                rel_path="",
            )
            scan_root = trusted.path

            # System Guardrails
            if root_id == "system":
                # Enforce safer defaults (Depth/Limit)
                if effective_max_depth > 6:
                    effective_max_depth = 6

                if effective_max_entries > 200000:
                    effective_max_entries = 200000

                # Enforce strict excludes for system root
                # Includes Linux/Pop!_OS standard paths + generic secrets
                hard_excludes = [
                    "**/.ssh/**", "**/.gnupg/**", "**/.password-store/**",
                    "**/.aws/**", "**/.kube/**",
                    "**/.mozilla/**", "**/.config/google-chrome/**", "**/.config/chromium/**",
                    "**/.local/share/keyrings/**",
                    "**/Keychain/**", "**/Safari/**"
                ]

                for ex in hard_excludes:
                    if ex not in effective_excludes:
                        effective_excludes.append(ex)

    except HTTPException as e:
         raise e

    # Generate ID
    scan_id = f"atlas-{int(time.time())}"

    # Define output paths
    merges_dir = state.merges_dir or get_merges_dir(hub)
    if not merges_dir.exists():
        merges_dir.mkdir(parents=True, exist_ok=True)

    json_filename = f"{scan_id}.json"
    md_filename = f"{scan_id}.md"
    inventory_filename = f"{scan_id}.inventory.jsonl" # Default name

    # Helper to run scan and save
    def run_scan_and_save():
        try:
            # Inventory First: inventory_file is always passed now.
            inventory_path = merges_dir / inventory_filename

            # Use inventory_strict if configured?
            # We don't have this in AtlasRequest yet (schema change).
            # But the user said: "Inventur-Default: ... (z.B. nur .git und offensichtliche Virtualenvs), damit der Nutzer wirklich 'alles beim Namen' bekommt."
            # and "Erlaube optional einen Modus 'inventur_strict=true'".
            # We should pass inventory_file.
            # And strict mode? If user didn't ask for specific excludes, maybe we should default to strict?
            # Or expose it.
            # Current instruction: "Default-Output is complete file list".
            # The AtlasScanner default excludes are NOT strict (they include node_modules etc).
            # To match the "Inventur" goal, we should probably set inventory_strict=True unless specified otherwise?
            # But wait, inventory_strict=True means LESS excludes.
            # So if we want "complete file list", we want strict mode.
            # Let's check existing logic:
            # inventory_strict=True -> only .git, .venv
            # inventory_strict=False -> .git, node_modules, cache, etc.

            # The requirement is "Primär-Output ist ein vollständiger Index".
            # "node_modules" usually is noise.
            # But "alles beim Namen" implies listing it.
            # Let's enable strict mode if no explicit excludes are given?
            # Or just pass inventory_file and let AtlasScanner defaults rule (which are SAFE/Clean).
            # The prompt said: "Phase 0 Ziel: Inventur... Keine Top N...".
            # It also said: "Default-Excludes dürfen existieren... Wichtig: Erlaube optional einen Modus 'inventur_strict=true'".
            # So Strict is OPTIONAL.

            # We will generate inventory file ALWAYS.

            scanner = AtlasScanner(
                root=scan_root,
                max_depth=effective_max_depth,
                max_entries=effective_max_entries,
                exclude_globs=effective_excludes,
                inventory_strict=False # Default safe. Can be exposed later.
            )
            result = scanner.scan(inventory_file=inventory_path)

            # Save JSON Stats
            with open(merges_dir / json_filename, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

            # Render and Save MD
            md_content = render_atlas_md(result)
            with open(merges_dir / md_filename, "w", encoding="utf-8") as f:
                f.write(md_content)

            logger.info(f"Atlas scan completed: {scan_id}")

        except Exception as e:
            logger.exception(f"Atlas scan failed: {e}")
            # Could save an error file?

    background_tasks.add_task(run_scan_and_save)

    # Update response object to include inventory path
    paths = {"json": json_filename, "md": md_filename, "inventory": inventory_filename}

    return AtlasArtifact(
        id=scan_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        hub=str(hub),
        root_scanned=str(scan_root),
        paths=paths,
        stats={}, # Empty initially
        effective=AtlasEffective(
            max_depth=effective_max_depth,
            max_entries=effective_max_entries,
            exclude_globs=effective_excludes
        )
    )

@app.post("/api/sync/metarepo", dependencies=[Depends(verify_token)])
def api_sync_metarepo(payload: Dict[str, Any]):
    """
    Trigger a metarepo synchronization (Manifest -> Fleet).
    Payload: { "mode": "dry_run"|"apply", "targets": ["wgx", "ci", ...] }
    """
    mode = payload.get("mode", "dry_run")
    if mode not in ("dry_run", "apply"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'dry_run' or 'apply'.")

    targets = payload.get("targets")
    if targets is not None and not isinstance(targets, list):
        raise HTTPException(status_code=400, detail="Targets must be a list of strings.")

    hub_path = state.hub
    if not hub_path:
        raise HTTPException(status_code=400, detail="Hub not configured")

    try:
        report = sync_from_metarepo(hub_path=hub_path, mode=mode, targets=targets)

        # IMPORTANT: do not return HTTP 200 for failed sync runs.
        # sync_from_metarepo must return {"status": "ok"|"error", ...}
        status = report.get("status")
        if status and status != "ok":
            msg = report.get("message") or report.get("error") or "Sync failed"
            # Treat as server-side failure of the sync feature contract.
            raise HTTPException(status_code=500, detail=msg)

        # Backward-compat: older error payloads used {"error": "..."} without status
        if "error" in report and report.get("error"):
            raise HTTPException(status_code=500, detail=str(report["error"]))

        return report
    except HTTPException:
        # Preserve explicit HTTP failures
        raise
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/atlas/latest", dependencies=[Depends(verify_token)])
def get_latest_atlas():
    merges_dir = state.merges_dir
    if not merges_dir and state.hub:
        merges_dir = get_merges_dir(state.hub)

    if not merges_dir or not merges_dir.exists():
        raise HTTPException(status_code=404, detail="No atlas artifacts found (no merges dir)")

    # Find atlas files
    # Pattern: atlas-{timestamp}.json
    files = list(merges_dir.glob("atlas-*.json"))
    if not files:
         raise HTTPException(status_code=404, detail="No atlas artifacts found")

    # Sort by name (timestamp) desc
    latest_file = sorted(files, key=lambda f: f.name, reverse=True)[0]

    # Load content for stats?
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            stats = data.get("stats", {})
            scan_root = data.get("root", "?")
    except Exception:
        stats = {}
        scan_root = "?"

    scan_id = latest_file.stem # atlas-123456

    # Construct paths
    paths = {"json": latest_file.name, "md": latest_file.with_suffix(".md").name}
    inv_file = latest_file.with_suffix(".inventory.jsonl")
    if inv_file.name.startswith(scan_id): # Ensure it matches ID (it does by construction)
         # Check existence? Usually assumed.
         # Actually check if it exists to avoid 404 links
         if inv_file.exists():
             paths["inventory"] = inv_file.name

    return AtlasArtifact(
        id=scan_id,
        created_at=datetime.fromtimestamp(latest_file.stat().st_mtime, timezone.utc).isoformat(),
        hub=str(state.hub),
        root_scanned=scan_root,
        paths=paths,
        stats=stats
    )

@app.get("/api/atlas/{id}/download", dependencies=[Depends(verify_token)])
def download_atlas(id: str, key: str = "md"):
    # Hard allowlist: atlas ids are generated as "atlas-<unix_ts>"
    if not re.fullmatch(r"atlas-\d+", (id or "").strip()):
        raise HTTPException(status_code=400, detail="Invalid atlas id format")

    if key not in ("json", "md", "inventory"):
        raise HTTPException(status_code=400, detail="Invalid key. Use 'json', 'md', or 'inventory'.")

    if not state.hub:
        raise HTTPException(status_code=400, detail="Hub not configured")

    merges_dir = (state.merges_dir or get_merges_dir(state.hub)).resolve()
    if not merges_dir.exists():
        raise HTTPException(status_code=404, detail="Merges directory not found")

    # IMPORTANT: do NOT build a path from user input.
    # Enumerate allowed files and then select by id.
    candidates = {}

    # Map key to extension
    ext_map = {"json": ".json", "md": ".md", "inventory": ".inventory.jsonl"}
    ext = ext_map[key]

    # Glob pattern needs to match suffix carefully
    # atlas-*.json covers .inventory.jsonl? No.
    # Globbing: atlas-*{ext}

    for p in merges_dir.glob(f"atlas-*{ext}"):
        try:
            rp = p.resolve()
            rp.relative_to(merges_dir)  # containment even under symlinks
        except Exception:
            continue

        # ID extraction:
        # atlas-123.json -> atlas-123
        # atlas-123.inventory.jsonl -> atlas-123 ?
        # stem of .inventory.jsonl is .inventory ? No.
        # pathlib stem logic:
        # p = atlas-123.inventory.jsonl -> stem = atlas-123.inventory
        # So p.stem != id.

        # Robust ID matching:
        if p.name.startswith(id + "."):
             candidates[id] = rp

    file_path = candidates.get(id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    # Unified file serving with security checks
    try:
        # Use relative_to for strict enforcement even if file_path came from glob()
        rel_path = file_path.relative_to(merges_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    return _serve_file(merges_dir, rel_path)

@app.post("/api/export/webmaschine", dependencies=[Depends(verify_token)])
def export_webmaschine():
    """
    Prepares an export directory for 'webmaschine'.
    """
    hub = state.hub
    if not hub:
        raise HTTPException(status_code=400, detail="Hub not configured")

    # User said: "Erzeugt Verzeichnis exports/webmaschine/"
    # Where? Usually relative to where repolens is running or the repo root?
    # Or inside the Hub? "hub/exports"?
    # "innerhalb des Repos" context suggests inside the tooling repo?
    # But repolensd runs on the user's machine on a "Hub".
    # Let's put it in `merges_dir/../exports/webmaschine` to be near output?
    # Or just `hub/exports`?
    # Let's try `hub/exports/webmaschine` if hub is writable.

    target_dir = hub / "exports" / "webmaschine"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "atlas").mkdir(exist_ok=True)
        (target_dir / "repos").mkdir(exist_ok=True)

        # 1. Copy latest Atlas
        # Reuse get_latest_atlas logic
        try:
            latest = get_latest_atlas()
            merges_dir = state.merges_dir or get_merges_dir(hub)

            import shutil
            shutil.copy2(merges_dir / latest.paths["json"], target_dir / "atlas" / "latest.json")
            shutil.copy2(merges_dir / latest.paths["md"], target_dir / "atlas" / "latest.md")
        except HTTPException:
            logger.warning("No atlas found to export")

        # 2. Export Repos Index
        # We can just dump _find_repos result
        from .runner import _find_repos
        repos = _find_repos(hub)
        with open(target_dir / "repos" / "index.json", "w", encoding="utf-8") as f:
            json.dump(repos, f, indent=2)

        # 3. Machine Definition (machine.json)
        machine_roots = []
        try:
            # Check if system is allowed/resolved (maps to Home)
            sys_root = Path.home().resolve()
            sec = get_security_config()
            sec.validate_path(sys_root)
            machine_roots.append(str(sys_root))
        except Exception as e:
            logger.debug("System root not available for export: %s", e, exc_info=True)

        machine_def = {
            "hub": str(hub.resolve()),
            "roots": machine_roots
        }

        with open(target_dir / "machine.json", "w", encoding="utf-8") as f:
            json.dump(machine_def, f, indent=2)

        # 4. README
        readme_content = """# Webmaschine Export

This directory contains the latest atlas and repository index from RepoLens.

## Update
Run `POST /api/export/webmaschine` to update these files.
"""
        with open(target_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        return {"status": "ok", "path": str(target_dir)}

    except Exception as e:
        logger.exception(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

# Serve static UI with Templating
# app.py is in lenskit/service. webui is in lenskit/frontends/webui.
current_dir = Path(__file__).parent
webui_dir = current_dir.parent / "frontends" / "webui"

# Pre-load raw template
_raw_index_template = None

def get_raw_index_template():
    global _raw_index_template
    if _raw_index_template is None:
        index_path = webui_dir / "index.html"
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            # Inject Build ID (Static per process)
            content = content.replace("__RLENS_BUILD__", BUILD_ID)
            _raw_index_template = content
        else:
            _raw_index_template = ""
    return _raw_index_template


@app.get("/ui", include_in_schema=False)
def ui_redirect(request: Request):
    # Dynamic redirect to a valid entry point
    # We redirect to /ui/ which is handled by serve_ui_index
    # and keeps the user under the /ui path segment (better for proxies)
    root_path = request.scope.get("root_path", "").rstrip("/")
    return RedirectResponse(url=f"{root_path}/ui/")

@app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
def serve_ui_index(request: Request):
    return serve_index(request)

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def serve_index(request: Request):
    content = get_raw_index_template()
    if not content:
         return HTMLResponse("<h1>rLens UI not found</h1>", status_code=404)

    # Dynamic Asset Base calculation
    # e.g. /prefix or ""
    root_path = request.scope.get("root_path", "").rstrip("/")

    # Asset base should point to where StaticFiles are mounted.
    # We mount at /ui. So base is {root_path}/ui/
    asset_base = f"{root_path}/ui/"

    final_content = content.replace("__RLENS_ASSET_BASE__", asset_base)

    headers = {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(final_content, headers=headers)

if webui_dir.exists():
    # Mount assets at /ui.
    # Note: explicit route @app.get("/ui/") defined above takes precedence
    # for exactly "/ui/", allowing us to serve the templated index there.
    # StaticFiles handles /ui/style.css, etc.
    app.mount("/ui", StaticFiles(directory=str(webui_dir), html=False), name="webui")
