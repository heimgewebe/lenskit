
import os
import json
import shutil
from pathlib import Path
from merger.lenskit.core.merge import write_reports_v2, FileInfo
from merger.lenskit.core.extractor import generate_review_bundle

# Setup
tmp_dir = Path("tmp_reproduction")
if tmp_dir.exists():
    shutil.rmtree(tmp_dir)
tmp_dir.mkdir()

merges_dir = tmp_dir / "merges"
merges_dir.mkdir()
hub_dir = tmp_dir / "hub"
hub_dir.mkdir()

# Dummy data
repo_name = "test_repo"
repo_root = hub_dir / repo_name
repo_root.mkdir()
(repo_root / "README.md").write_text("# Test Repo\n\nContent.", encoding="utf-8")
(repo_root / "src").mkdir()
(repo_root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")

# FileInfo objects
files = [
    FileInfo(
        root_label=repo_name,
        abs_path=repo_root / "README.md",
        rel_path=Path("README.md"),
        size=len((repo_root / "README.md").read_bytes()),
        is_text=True,
        md5="md5checksum",
        category="doc",
        tags=["ai-context"],
        ext=".md"
    ),
    FileInfo(
        root_label=repo_name,
        abs_path=repo_root / "src" / "main.py",
        rel_path=Path("src/main.py"),
        size=len((repo_root / "src" / "main.py").read_bytes()),
        is_text=True,
        md5="md5checksum2",
        category="source",
        tags=[],
        ext=".py"
    )
]

repo_summary = {
    "name": repo_name,
    "root": repo_root,
    "files": files
}

# 1. Generate Report artifacts
print("Generating reports...")
write_reports_v2(
    merges_dir=merges_dir,
    hub=hub_dir,
    repo_summaries=[repo_summary],
    detail="max",
    mode="single", # or gesamt, but for single repo it behaves similarly in list wrapping
    max_bytes=1000,
    plan_only=False,
    extras=type('Extras', (object,), {'json_sidecar': True, 'health': False, 'organism_index': False, 'fleet_panorama': False, 'augment_sidecar': False, 'delta_reports': False, 'heatmap': False, 'none': lambda: None})()
)

# Verify Report Artifacts
print("\n--- Verifying Report Artifacts ---")
dump_index = list(merges_dir.glob("*.dump_index.json"))[0]
print(f"Found dump index: {dump_index.name}")
data = json.loads(dump_index.read_text())

print("Checking dump_index generator info...")
if "config_sha256" in data.get("generator", {}):
    print("  [OK] config_sha256 present")
else:
    print("  [FAIL] config_sha256 missing")

print("Checking dump_index artifacts...")
artifacts = data.get("artifacts", {})
required_fields = ["content_type", "bytes", "role", "sha256"]
for role, art in artifacts.items():
    missing = [f for f in required_fields if f not in art]
    if missing:
        print(f"  [FAIL] Artifact {role} missing fields: {missing}")
    else:
        print(f"  [OK] Artifact {role} has all fields. Type: {art['content_type']}")

# Sidecar
sidecar = list(merges_dir.glob("*.json"))
sidecar = [p for p in sidecar if not p.name.endswith(".dump_index.json")][0]
print(f"Found sidecar: {sidecar.name}")
sdata = json.loads(sidecar.read_text())
meta = sdata.get("meta", {})
print("Checking sidecar meta fields...")
for f in ["output_mode", "include_hidden", "redact_secrets", "split_size_bytes", "max_bytes", "schema_ids"]:
    if f in meta:
        print(f"  [OK] {f} present: {meta[f]}")
    else:
        print(f"  [FAIL] {f} missing")

# Reading Policy
rp = sdata.get("reading_policy", {})
print("Checking reading policy...")
if "canonical_content_artifact" in rp and "navigation_artifacts" in rp:
    print("  [OK] Reading policy looks operational")
else:
    print("  [FAIL] Reading policy outdated")

# Architecture
arch = list(merges_dir.glob("*_architecture.md"))[0]
print(f"Found architecture summary: {arch.name}")
atext = arch.read_text()
if "<!-- ARTIFACT:architecture_summary" in atext:
    print("  [OK] Sentinel header present")
else:
    print("  [FAIL] Sentinel header missing")
if "## LAYER_DISTRIBUTION" in atext:
    print("  [OK] Machine-friendly header present")
else:
    print("  [FAIL] Machine-friendly header missing")

# Merge MD
md = list(merges_dir.glob("*_merge.md"))[0]
print(f"Found merge markdown: {md.name}")
mtext = md.read_text()
if "<!-- READING_POLICY" in mtext:
    print("  [OK] Reading policy sentinel present")
else:
    print("  [FAIL] Reading policy sentinel missing")
if "<!-- FILE_START" in mtext and "<!-- FILE_END" in mtext:
    print("  [OK] File markers present")
else:
    print("  [FAIL] File markers missing")


# 2. Generate Bundle
print("\nGenerating review bundle...")
# Create a "new" repo state for bundle gen
repo_root_new = tmp_dir / "hub_new" / repo_name
if repo_root_new.exists(): shutil.rmtree(repo_root_new)
shutil.copytree(repo_root, repo_root_new)
(repo_root_new / "new_file.txt").write_text("new", encoding="utf-8")

try:
    generate_review_bundle(repo_root, repo_root_new, repo_name, hub_dir)
except Exception as e:
    print(f"Bundle generation failed: {e}")

# Find bundle
bundle_dir = list((hub_dir / ".repolens/pr-schau" / repo_name).glob("*"))[0]
bundle_json_path = bundle_dir / "bundle.json"
print(f"Found bundle: {bundle_json_path}")

bdata = json.loads(bundle_json_path.read_text())
print("Checking bundle artifacts...")
b_artifacts = bdata.get("artifacts", [])
for ba in b_artifacts:
    missing = [f for f in ["content_type", "role"] if f not in ba] # bytes is optional for self-ref index
    if missing:
        print(f"  [FAIL] Bundle artifact {ba.get('basename')} missing fields: {missing}")
    else:
        print(f"  [OK] Bundle artifact {ba.get('basename')} has fields. Role: {ba['role']}")

print("\nReproduction complete.")
