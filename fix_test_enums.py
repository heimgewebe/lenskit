with open("merger/lenskit/tests/test_cli_atlas_diff_label.py", "r") as f:
    content = f.read()

content = content.replace("from merger.lenskit.cli.cmd_atlas import _resolve_snapshot_ref, parse_snapshot_ref",
                          "from merger.lenskit.cli.cmd_atlas import _resolve_snapshot_ref, parse_snapshot_ref, SnapshotRefKind")

content = content.replace('assert parsed.kind.value == "snapshot_id"', 'assert parsed.kind == SnapshotRefKind.SNAPSHOT_ID')
content = content.replace('assert parsed.kind.value == "machine_path"', 'assert parsed.kind == SnapshotRefKind.MACHINE_PATH')
content = content.replace('assert parsed.kind.value == "machine_label"', 'assert parsed.kind == SnapshotRefKind.MACHINE_LABEL')

content = content.replace('assert parsed2.kind.value == "machine_path"', 'assert parsed2.kind == SnapshotRefKind.MACHINE_PATH')

with open("merger/lenskit/tests/test_cli_atlas_diff_label.py", "w") as f:
    f.write(content)
