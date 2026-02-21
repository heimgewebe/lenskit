from pathlib import Path

from merger.lenskit.core import merge
from merger.lenskit.core.merge import FileInfo


def create_file_info(rel_path: str, category: str = "other", tags=None, content: str = "content") -> FileInfo:
    return FileInfo(
        root_label="test-repo",
        abs_path=Path("/tmp") / rel_path,
        rel_path=Path(rel_path),
        size=len(content),
        is_text=True,
        md5="md5sum",
        category=category,
        tags=tags or [],
        ext=Path(rel_path).suffix,
        content=content,
        inclusion_reason="normal",
    )


def test_path_filter_hard_include_excludes_critical_files():
    """
    path_filter wirkt als harter Include-Filter für Manifest und Content:
    - Nur matching paths werden aufgenommen
    - Auch "critical" files (README, workflows) fliegen raus, wenn sie nicht matchen
    """
    files = [
        create_file_info("docs/adr/001-decision.md", category="doc", tags=["adr"]),
        create_file_info("README.md", category="doc", tags=["ai-context"]),  # "critical"
        create_file_info(".github/workflows/main.yml", category="config", tags=["ci"]),  # "critical"
    ]

    report = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[Path("/tmp/test-repo")],
            plan_only=False,
            path_filter="docs/adr",
            meta_density="standard",
        )
    )

    # Positive: ADR-File wird wirklich gerendert (stabiler Marker: File-Block Path-Zeile)
    assert "**Path:** `docs/adr/001-decision.md`" in report

    # Negative: Nicht-matching "critical" files dürfen NICHT gerendert werden
    assert "**Path:** `README.md`" not in report
    assert "**Path:** `.github/workflows/main.yml`" not in report


def test_meta_density_min_gates_hotspots_and_reading_lenses_everywhere(monkeypatch):
    """
    meta_density='min' muss Hotspots (Plan) und Reading Lenses deaktivieren.
    Deterministisch via monkeypatch: build_hotspots liefert garantiert etwas,
    damit wir das Gate testen (nicht die Heuristik).
    """
    files = [
        create_file_info("src/main.py", category="source", tags=["entrypoint"]),
        create_file_info("docs/readme.md", category="doc"),
    ]

    def fake_build_hotspots(_processed_files, **kwargs):
        return ["### Hotspots (Einstiegspunkte)\n- fake\n"]

    monkeypatch.setattr(merge, "build_hotspots", fake_build_hotspots)

    report = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[Path("/tmp/test-repo")],
            plan_only=False,
            meta_density="min",
        )
    )

    # Content ist da
    assert "**Path:** `src/main.py`" in report

    # Gate muss greifen
    assert "Hotspots (Einstiegspunkte)" not in report
    assert "Reading Lenses" not in report


def test_meta_density_standard_allows_hotspots(monkeypatch):
    """
    Kontrolltest: meta_density='standard' darf Hotspots zulassen.
    Wieder deterministisch: build_hotspots wird gepatcht.
    """
    files = [create_file_info("src/main.py", category="source", tags=["entrypoint"])]

    def fake_build_hotspots(_processed_files, **kwargs):
        return ["### Hotspots (Einstiegspunkte)\n- fake\n"]

    monkeypatch.setattr(merge, "build_hotspots", fake_build_hotspots)

    report = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[Path("/tmp/test-repo")],
            plan_only=False,
            meta_density="standard",
        )
    )

    assert "Hotspots (Einstiegspunkte)" in report


def test_auto_warning_only_on_actual_auto_downgrade():
    """
    Auto-Warnung nur wenn auto -> standard wegen Filtern.
    Fälle:
    1) auto + filter -> Warnung
    2) standard + filter -> KEINE Warnung
    3) auto ohne filter -> KEINE Warnung
    """
    files = [create_file_info("test.txt")]

    # 1) Auto + Filter -> Warning
    report1 = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[],
            plan_only=False,
            path_filter="test",
            meta_density="auto",
        )
    )
    assert "⚠️ **Auto-Drosselung:**" in report1

    # 2) Standard + Filter -> No Warning
    report2 = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[],
            plan_only=False,
            path_filter="test",
            meta_density="standard",
        )
    )
    assert "⚠️ **Auto-Drosselung:**" not in report2

    # 3) Auto ohne Filter -> No Warning (auto resolves to full, no downgrade)
    report3 = "".join(
        merge.iter_report_blocks(
            files=files,
            level="max",
            max_file_bytes=0,
            sources=[],
            plan_only=False,
            meta_density="auto",
        )
    )
    assert "⚠️ **Auto-Drosselung:**" not in report3
