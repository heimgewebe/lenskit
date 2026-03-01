with open("merger/lenskit/tests/test_bundle_manifest_integration.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_header = """import json
import re
from pathlib import Path

import jsonschema
import pytest

from merger.lenskit.core.constants import ArtifactRole
from merger.lenskit.core.merge import FileInfo, write_reports_v2
from merger.lenskit.tests._test_constants import make_generator_info

"""

start_idx = 0
for i, line in enumerate(lines):
    if line.startswith("class MockExtras:"):
        start_idx = i
        break

new_lines = [new_header] + lines[start_idx:]

with open("merger/lenskit/tests/test_bundle_manifest_integration.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
