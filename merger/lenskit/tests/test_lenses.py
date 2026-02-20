import pytest
from pathlib import Path
from merger.lenskit.core.lenses import infer_lens

@pytest.mark.parametrize("path,expected", [
    # Guards
    (Path(".github/workflows/main.yml"), "guards"),
    (Path("wgx/config.json"), "guards"),
    (Path("tests/test_basic.py"), "guards"),

    # Data Models
    (Path("src/contracts/user.proto"), "data_models"),
    (Path("src/schemas/event.schema.json"), "data_models"),
    (Path("models.py"), "data_models"),

    # Pipelines
    (Path("src/pipelines/daily_sync.py"), "pipelines"),
    (Path("airflow/workflows/dag.py"), "pipelines"),

    # Entrypoints
    (Path("src/__main__.py"), "entrypoints"),
    (Path("manage.py"), "entrypoints"),
    (Path("docs/README.md"), "entrypoints"), # Decided: README in docs is entrypoints

    # UI
    (Path("src/ui/button.tsx"), "ui"), # Matches 'ui' in parts
    (Path("style.css"), "ui"),
    (Path("templates/index.html"), "ui"),

    # Interfaces
    (Path("src/api/v1/users.py"), "interfaces"),
    (Path("src/service/user_service.py"), "interfaces"),

    # Core
    (Path("src/logic/calculator.py"), "core"),
    (Path("src/domain/entity.py"), "core"),
    (Path("engine.py"), "core"),
])
def test_infer_lens_markers(path, expected):
    """Tests high-signal markers for each lens ID."""
    assert infer_lens(path) == expected


@pytest.mark.parametrize("path,expected", [
    # core beats service
    (Path("src/core/service/logic.py"), "core"),
    # guards beats data_models
    (Path("tests/models.py"), "guards"),
    # guards beats entrypoints
    (Path(".github/bin/script.sh"), "guards"),
])
def test_infer_lens_precedence(path, expected):
    """Tests precedence rules between different heuristics."""
    assert infer_lens(path) == expected


def test_infer_lens_fallback():
    """Tests the ultimate fallback for unknown files."""
    assert infer_lens(Path("misc/unknown_file.xyz")) == "core"
