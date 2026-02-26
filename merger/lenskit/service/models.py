from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
import uuid
import hashlib
import json
from datetime import datetime, timezone

def calculate_job_hash(req: "JobRequest", hub_resolved: str, version: str) -> str:
    """
    Calculates a deterministic hash for the job parameters to ensure idempotency.
    Includes 'version' to ensure reproducibility across software updates.
    """
    # Normalize extras
    extras_list = sorted([x.strip().lower() for x in (req.extras or "").split(",") if x.strip()])
    extras_str = ",".join(extras_list)

    # Normalize path_filter (None vs "")
    path_filter = req.path_filter.strip() if isinstance(req.path_filter, str) else None
    if path_filter == "":
        path_filter = None

    # Normalize repos
    repos_list = sorted(req.repos) if req.repos else ["__ALL__"]

    # Normalize extensions
    ext_list = sorted(req.extensions) if req.extensions else []

    # Normalize include_paths
    inc_paths = None
    if req.include_paths is not None:
        if any(p in (".", "") for p in req.include_paths):
            inc_paths = None
        else:
            inc_paths = sorted(req.include_paths)

    # Construct signature dict
    sig = {
        "lenskit_version": version,
        "hub": hub_resolved, # Use resolved hub path!
        "repos": repos_list,
        "level": req.level,
        "mode": req.mode,
        "max_bytes": req.max_bytes,
        "split_size": req.split_size,
        "plan_only": req.plan_only,
        "code_only": req.code_only,
        "extensions": ext_list,
        "path_filter": path_filter,
        "extras": extras_str,
        "json_sidecar": req.json_sidecar,
        "meta_density": req.meta_density,
        "include_paths": inc_paths,
        # New fields v2.4
        "output_mode": req.output_mode,
        "redact_secrets": req.redact_secrets,
        "include_hidden": req.include_hidden,
        # Merges dir excluded from content hash:
        # Same content, different output path = same logical job.
        # Client must check returned artifact for actual path.
    }

    # Serialize and hash
    sig_str = json.dumps(sig, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

class JobRequest(BaseModel):
    hub: Optional[str] = None
    merges_dir: Optional[str] = None # Output directory override
    repos: Optional[List[str]] = None  # None/empty = all
    level: Literal["overview", "summary", "dev", "max"] = "dev"
    mode: Literal["gesamt", "pro-repo"] = "gesamt"
    max_bytes: Optional[str] = "0"  # human size string or "0"
    split_size: Optional[str] = "25MB"
    plan_only: bool = False
    code_only: bool = False
    extensions: Optional[List[str]] = None
    path_filter: Optional[str] = None
    include_paths: Optional[List[str]] = None # Relative paths to include (whitelist)
    include_paths_by_repo: Optional[Dict[str, Optional[List[str]]]] = None
    strict_include_paths_by_repo: bool = False # If True, missing keys in include_paths_by_repo trigger hard fail (400)
    # Default: Minimal (Agent-fokussiert). Nur Sidecars.
    # Aligning with repolens.py logic to prevent drift.
    extras: Optional[str] = "json_sidecar,augment_sidecar"
    meta_density: Literal["min", "standard", "full", "auto"] = Field(
        default="auto",
        description="Controls the density of metadata (headers, file_meta blocks) in the report. 'auto' switches to 'standard' if filters are active."
    )
    json_sidecar: bool = True  # Default true for service
    force_new: bool = False
    # v2.4 Parity Features
    output_mode: Literal["archive", "retrieval", "dual"] = "dual"
    redact_secrets: bool = False
    include_hidden: bool = Field(default=True, description="Whether to include hidden files/directories (starting with .)")

class AtlasEffective(BaseModel):
    max_depth: int
    max_entries: int
    exclude_globs: List[str]

class AtlasRequest(BaseModel):
    # Canonical: token from FS picker (opaque, HMAC-signed by server).
    # This avoids user-controlled path expressions and satisfies CodeQL.
    root_token: Optional[str] = None

    # Transitional: allow selecting a known root id ("hub" | "merges" | "system").
    # NOTE: Do NOT accept arbitrary paths here; use root_token instead.
    root_id: Optional[str] = None

    root: Optional[str] = None  # Deprecated.
    max_depth: int = 6
    max_entries: int = 200000
    exclude_globs: Optional[List[str]] = None
    sample_files: bool = False

class AtlasArtifact(BaseModel):
    id: str
    created_at: str
    hub: str
    root_scanned: str
    paths: Dict[str, str] # {"json": "...", "md": "..."}
    stats: Dict[str, Any] # Summary stats
    effective: Optional[AtlasEffective] = None # Effective parameters (max_depth, etc)

class Artifact(BaseModel):
    id: str
    job_id: str
    hub: str
    repos: List[str]
    created_at: str
    paths: Dict[str, str]  # e.g. {"md": "...", "json": "...", "part2": "..."}
    params: JobRequest # Effective parameters used for generation (normalized)
    merges_dir: Optional[str] = None # Effective absolute path to output directory

class Job(BaseModel):
    id: str
    # 'canceling' = user requested cancel, runner hasn't stopped yet
    # 'canceled' = final state
    status: Literal["queued", "running", "succeeded", "failed", "canceling", "canceled"]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    request: JobRequest
    hub_resolved: Optional[str] = None
    content_hash: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    artifact_ids: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    @classmethod
    def create(cls, request: JobRequest, content_hash: Optional[str] = None) -> "Job":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=str(uuid.uuid4()),
            status="queued",
            created_at=now,
            request=request,
            content_hash=content_hash,
            logs=[],
            warnings=[],
            artifact_ids=[]
        )

class PrescanRequest(BaseModel):
    repo: str # Repo name to scan
    max_depth: int = 10
    ignore_globs: Optional[List[str]] = None

class PrescanNode(BaseModel):
    path: str
    type: Literal["file", "dir"]
    size: Optional[int] = None
    children: Optional[List["PrescanNode"]] = None

try:
    PrescanNode.model_rebuild()
except AttributeError:
    # Fallback for Pydantic v1
    try:
        PrescanNode.update_forward_refs()
    except AttributeError:
        pass

class PrescanResponse(BaseModel):
    root: str
    tree: PrescanNode
    signature: str
    file_count: int
    total_bytes: int

class FSRoot(BaseModel):
    id: str
    path: str
    token: str

class FSRootsResponse(BaseModel):
    roots: List[FSRoot]
