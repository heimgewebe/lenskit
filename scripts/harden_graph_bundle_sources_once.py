from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content.rstrip() + "\n", encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    write(path, content.replace(old, new, 1))


def patch_merge() -> None:
    path = "merger/lenskit/core/merge.py"
    replace_once(
        path,
        "        from ..architecture.bundle_sources import ensure_bundle_graph_sources\n",
        """        from ..architecture.bundle_sources import (
            BundleGraphSourceError,
            ensure_bundle_graph_sources,
        )
""",
    )
    replace_once(
        path,
        """        source_result = ensure_bundle_graph_sources(
            base_path=base_path,
            repo_summaries=repo_summaries,
""",
        """        source_result = ensure_bundle_graph_sources(
            base_path=base_path,
            chunk_index_path=chunk_path,
            repo_summaries=repo_summaries,
""",
    )
    replace_once(
        path,
        """        architecture_graph_path = source_result.graph_path
        entrypoints_path = source_result.entrypoints_path

        for source_path in (architecture_graph_path, entrypoints_path):
""",
        """        architecture_graph_path = source_result.graph_path
        entrypoints_path = source_result.entrypoints_path
        if debug and source_result.reason:
            print(
                f"Graph source production {source_result.status}: "
                f"{source_result.reason}",
                file=sys.stderr,
            )

        for source_path in (architecture_graph_path, entrypoints_path):
""",
    )
    replace_once(
        path,
        """    except GraphIndexCompilationError:
        raise
    except Exception as e:
        if debug:
            print(f"Error producing graph artifacts: {e}", file=sys.stderr)

""",
        """    except (BundleGraphSourceError, GraphIndexCompilationError):
        raise
    except Exception as e:
        if debug:
            print(f"Error producing graph artifacts: {e}", file=sys.stderr)
        raise

""",
    )
    replace_once(
        path,
        "hub, generator_info, [s_name], debug, repo_summaries=[s]\n",
        """hub, generator_info, [s_name], debug,
                    repo_summaries=[s] if len(repo_summaries) == 1 else None,
""",
    )


def patch_integration_test() -> None:
    path = "merger/lenskit/tests/test_graph_bundle_integration.py"
    content = read(path)
    if "from merger.lenskit.architecture import bundle_sources\n" not in content:
        content = content.replace(
            "import pytest\n\n",
            """import pytest

from merger.lenskit.architecture import bundle_sources
from merger.lenskit.architecture.bundle_sources import BundleGraphSourceError
""",
            1,
        )
    content = content.replace(
        '    args["repo_summaries"] = [{"root": repo_root, "name": "repo1"}]\n',
        '''    args["chunk_path"].write_text(
        json.dumps(
            {
                "repo": "repo1",
                "path": "main.py",
                "source_status": "full",
                "truncated": False,
                "source_range": {"status": "declared"},
            }
        )
        + "\\n",
        encoding="utf-8",
    )
    args["repo_summaries"] = [{"root": repo_root, "name": "repo1"}]
''',
        1,
    )
    content = content.replace(
        '    assert graph["nodes"][0]["repo"] == "repo1"\n',
        '''    file_nodes = [node for node in graph["nodes"] if node["kind"] == "file"]
    assert [(node["path"], node["repo"]) for node in file_nodes] == [
        ("main.py", "repo1")
    ]
''',
        1,
    )
    test = '''


def test_graph_bundle_propagates_source_production_failure(tmp_path, monkeypatch):
    base, _, args = _setup(tmp_path)

    def fail_production(**kwargs):
        raise BundleGraphSourceError("simulated source production failure")

    monkeypatch.setattr(bundle_sources, "ensure_bundle_graph_sources", fail_production)

    with pytest.raises(BundleGraphSourceError, match="simulated source production"):
        build_derived_artifacts(**args)

    assert not base.with_suffix(".graph_index.json").exists()
'''
    if "test_graph_bundle_propagates_source_production_failure" not in content:
        content = content.rstrip() + test + "\n"
    write(path, content)


def patch_manifest_test() -> None:
    path = "merger/lenskit/tests/test_graph_bundle_manifest_provenance.py"
    content = read(path)
    addition = '''

    source_expectations = {
        ArtifactRole.ARCHITECTURE_GRAPH_JSON.value: "architecture.graph",
        ArtifactRole.ENTRYPOINTS_JSON.value: "entrypoints",
    }
    for role, contract_id in source_expectations.items():
        entries = [
            artifact
            for artifact in manifest["artifacts"]
            if artifact.get("role") == role
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["contract"] == {"id": contract_id, "version": "v1"}
        assert entry["authority"] == "diagnostic_signal"
        assert entry["canonicality"] == "diagnostic"
        assert entry["regenerable"] is True
        assert entry["staleness_sensitive"] is True
'''
    marker = '    assert graph_entry["staleness_sensitive"] is True\n'
    if addition.strip() not in content:
        if content.count(marker) != 1:
            raise RuntimeError("manifest source assertion anchor changed")
        content = content.replace(marker, marker + addition, 1)
    write(path, content)


def normalize_schema_diff() -> None:
    path = "merger/lenskit/contracts/bundle-manifest.v1.schema.json"
    content = read(path)
    content = re.sub(
        r'"type": \[\n\s+"(string|boolean)",\n\s+"null"\n\s+\]',
        r'"type": ["\1", "null"]',
        content,
    )
    content = re.sub(
        r'"required": \[\n\s+"risk_class"\n\s+\]',
        '"required": ["risk_class"]',
        content,
    )
    write(path, content)


def patch_proof() -> None:
    path = "docs/proofs/graph-bundle-source-production-proof.md"
    content = read(path)
    old = """For retrieval or dual output, the ordinary merge pipeline now creates
`architecture.graph.v1` and `entrypoints.v1` source artifacts when the output
contains exactly one repository and neither source already exists. Both sources
receive the actual bundle run ID and finalized dump-index SHA-256. The graph's
`generated_at` is replaced with the merge clock value, and file nodes carry the
repository name.
"""
    new = """For retrieval or dual output, the ordinary merge pipeline now creates
`architecture.graph.v1` and `entrypoints.v1` source artifacts when the output
contains exactly one repository and neither source already exists. Both sources
receive the actual bundle run ID and finalized dump-index SHA-256. The graph's
`generated_at` is replaced with the merge clock value, and file nodes carry the
repository name.

The producer derives its Python source set from the emitted chunk index rather
than rescanning the complete repository. Only paths with full source contact,
without truncation and with declared source coordinates, are materialized into a
temporary filtered tree for static analysis. Redacted, truncated, unverifiable,
or out-of-scope files cannot silently influence the retrieval Graph Index.
"""
    if old not in content:
        raise RuntimeError("proof source-boundary paragraph changed")
    content = content.replace(old, new, 1)
    write(path, content)


def main() -> None:
    patch_merge()
    patch_integration_test()
    patch_manifest_test()
    normalize_schema_diff()
    patch_proof()


if __name__ == "__main__":
    main()
