import pytest
from pathlib import Path
from merger.lenskit.core.lenses import infer_lens

@pytest.mark.parametrize("path,expected", [
    # Guards
    (Path(".github/workflows/main.yml"), "guards"),
    (Path("wgx/config.json"), "guards"),
    (Path("src/guards/auth.py"), "guards"),
    (Path("tests/test_basic.py"), "guards"),
    (Path("src/test/utils.py"), "guards"),
    (Path("src/test_logic.py"), "guards"),
    (Path("src/logic_test.py"), "guards"),
    (Path("src/logic.test.ts"), "guards"),
    (Path("src/logic.spec.ts"), "guards"),
    (Path("src/validate_input.py"), "guards"),
    (Path("src/validation_logic.py"), "guards"),

    # Data Models
    (Path("src/contracts/user.proto"), "data_models"),
    (Path("src/schemas/event.json"), "data_models"),
    (Path("src/models/db.py"), "data_models"),
    (Path("src/types/common.ts"), "data_models"),
    (Path("docs/api.schema.json"), "data_models"),
    (Path("proto/service.proto"), "data_models"),
    (Path("thrift/service.thrift"), "data_models"),
    (Path("src/structs.rs"), "data_models"),
    (Path("src/types.ts"), "data_models"),
    (Path("src/models.py"), "data_models"),
    (Path("config.json"), "data_models"),
    (Path("settings.yaml"), "data_models"),
    (Path("manifest.yml"), "data_models"),
    (Path("pyproject.toml"), "data_models"),

    # Pipelines
    (Path("src/pipelines/daily_sync.py"), "pipelines"),
    (Path("jobs/batch_process.py"), "pipelines"),
    (Path("src/orchestration/flow.py"), "pipelines"),
    (Path("airflow/workflows/dag.py"), "pipelines"),

    # Entrypoints
    (Path("frontends/mobile/main.dart"), "entrypoints"),
    (Path("src/cli/parser.py"), "entrypoints"),
    (Path("bin/setup.sh"), "entrypoints"),
    (Path("src/__main__.py"), "entrypoints"),
    (Path("src/main.rs"), "entrypoints"),
    (Path("src/index.ts"), "entrypoints"),
    (Path("src/index.js"), "entrypoints"),
    (Path("src/run_server.py"), "entrypoints"),
    (Path("src/start_app.py"), "entrypoints"),
    (Path("manage.py"), "entrypoints"),
    (Path("docs/README.md"), "entrypoints"),

    # UI
    (Path("src/ui/button.tsx"), "ui"),
    (Path("src/app/component.js"), "ui"),
    (Path("src/web/styles.css"), "ui"),
    (Path("src/frontend/assets/logo.png"), "ui"),
    (Path("src/views/home.html"), "ui"),
    (Path("src/templates/email.html"), "ui"),
    (Path("components/header.svelte"), "ui"),
    (Path("assets/main.css"), "ui"),

    # Interfaces
    (Path("src/adapters/sql_adapter.py"), "interfaces"),
    (Path("src/interfaces/repository.py"), "interfaces"),
    (Path("src/api/v1/users.py"), "interfaces"),
    (Path("src/ports/input.py"), "interfaces"),
    (Path("src/routes/api.py"), "interfaces"),
    (Path("src/service/user_service.py"), "interfaces"),

    # Core
    (Path("src/core/engine.py"), "core"),
    (Path("src/logic/calculator.py"), "core"),
    (Path("src/domain/entity.py"), "core"),
    (Path("src/utils.py"), "core"),
    (Path("src/main.go"), "core"),
    (Path("src/lib.rs"), "core"),
    (Path("src/app.ts"), "core"),
    (Path("src/script.js"), "core"),
    (Path("src/native.java"), "core"),
    (Path("src/main.c"), "core"),
    (Path("src/lib.cpp"), "core"),

    # Edge cases
    (Path("src/core/service/logic.py"), "core"), # core takes precedence over service
    (Path("README.txt"), "core"), # Ultimate fallback
])
def test_infer_lens(path, expected):
    assert infer_lens(path) == expected
