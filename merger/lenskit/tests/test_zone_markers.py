import sys
import os
import re
from pathlib import Path

# Add merger/ to sys.path so lenskit is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from lenskit.core.merge import iter_report_blocks, FileInfo, ExtrasConfig

def test_zone_markers_symmetry():
    """
    Verifies that every <!-- zone:begin ... --> tag has a corresponding
    <!-- zone:end ... --> tag with identical type and id attributes.
    """
    # Create dummy files
    files = [
        FileInfo(
            root_label="repo",
            abs_path=Path("dummy.py"),
            rel_path=Path("dummy.py"),
            size=10,
            is_text=True,
            md5="dummy",
            category="source",
            tags=[],
            ext=".py",
            content="print('hello')"
        )
    ]

    # Generate report content stream
    iterator = iter_report_blocks(
        files=files,
        level="max",
        max_file_bytes=1000,
        sources=[Path("repo")],
        plan_only=False,
        extras=ExtrasConfig(json_sidecar=True)
    )

    report_content = "".join(iterator)

    # Regex to find zone markers
    # Captures: 1=begin|end, 2=attributes
    zone_pattern = re.compile(r"<!-- zone:(begin|end)\s+(.+?)\s*-->")

    zones = []

    for match in zone_pattern.finditer(report_content):
        kind = match.group(1) # begin or end
        attrs_str = match.group(2)

        # Parse attributes (naive splitting by space, assuming no spaces in values for now or quotes)
        # Better: use regex to parse key=value
        attr_pattern = re.compile(r'([a-zA-Z0-9_]+)=(".*?"|\S+)')
        attrs = {}
        for am in attr_pattern.finditer(attrs_str):
            key = am.group(1)
            val = am.group(2).strip('"')
            attrs[key] = val

        zones.append({"kind": kind, "attrs": attrs, "raw": match.group(0)})

    # Stack for validating nesting and symmetry
    stack = []

    for z in zones:
        if z["kind"] == "begin":
            stack.append(z)
        elif z["kind"] == "end":
            assert len(stack) > 0, f"Found zone:end without zone:begin: {z['raw']}"
            start_zone = stack.pop()

            # Check Symmetry
            # 1. Type must match
            assert start_zone["attrs"].get("type") == z["attrs"].get("type"), \
                f"Zone type mismatch: {start_zone['raw']} vs {z['raw']}"

            # 2. ID must match
            # Note: id is required for strict symmetry
            start_id = start_zone["attrs"].get("id")
            end_id = z["attrs"].get("id")

            assert start_id is not None, f"zone:begin missing id: {start_zone['raw']}"
            assert end_id is not None, f"zone:end missing id: {z['raw']}"
            assert start_id == end_id, f"Zone ID mismatch: {start_zone['raw']} vs {z['raw']}"

    assert len(stack) == 0, f"Unclosed zones remaining: {[z['raw'] for z in stack]}"

if __name__ == "__main__":
    test_zone_markers_symmetry()
