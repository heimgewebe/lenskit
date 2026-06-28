from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def patch_workflow() -> None:
    path = ".github/workflows/graph-model.yml"
    content = read(path)

    path_anchor = '      - "merger/lenskit/tests/test_graph_eval.py"\n'
    path_addition = '      - "merger/lenskit/tests/test_retrieval_query.py"\n'
    if path_addition not in content:
        if content.count(path_anchor) != 2:
            raise SystemExit("graph workflow path-filter anchor changed")
        content = content.replace(path_anchor, path_anchor + path_addition)

    slash = "\\"
    pytest_anchor = (
        "            merger/lenskit/tests/test_graph_eval.py " + slash + "\n"
    )
    pytest_addition = (
        "            merger/lenskit/tests/test_retrieval_query.py " + slash + "\n"
    )
    if pytest_addition not in content:
        if content.count(pytest_anchor) != 1:
            raise SystemExit("graph workflow pytest anchor changed")
        content = content.replace(
            pytest_anchor,
            pytest_anchor + pytest_addition,
            1,
        )

    ruff_anchor = (
        "            merger/lenskit/cli/cmd_architecture.py " + slash + "\n"
    )
    ruff_addition = "".join(
        f"            {item} {slash}\n"
        for item in (
            "merger/lenskit/retrieval/query_core.py",
            "merger/lenskit/tests/test_graph_rerank.py",
            "merger/lenskit/tests/test_retrieval_query.py",
        )
    )
    if ruff_addition not in content:
        if content.count(ruff_anchor) != 1:
            raise SystemExit("graph workflow Ruff anchor changed")
        content = content.replace(
            ruff_anchor,
            ruff_anchor + ruff_addition,
            1,
        )

    write(path, content)


def patch_contract() -> None:
    path = "docs/architecture/graph-runtime-contract.md"
    content = read(path)
    content = content.replace(
        '* `unreadable` → IO-Fehler (z.B. fehlende Leserechte).',
        '* `unreadable` → IO-Fehler (z.B. fehlende Leserechte).\n'
        '* `invalid_path` → Der relative Artefaktpfad verletzt die Root-Grenze; der Graph wird nicht geladen.',
    )
    section = '''

## 5. Pfad-Sicherheitsgrenze

Ein explizit gewählter Graph Index muss entweder als einfacher Geschwister-Dateiname angegeben werden oder als absoluter Pfad, dessen lexikalischer Elternordner dem Ordner des SQLite-Index entspricht. Die Query-Runtime löst den nutzerbestimmten Graph-Pfad nicht im Dateisystem auf. Sie übergibt ausschließlich den geprüften Dateinamen an den root-gebundenen Loader, der den gemeinsamen Pfad-Sicherheitshelfer verwendet.

Ein Verstoß gegen diese Ortsgrenze ist ein harter Aufruferfehler. Ein vom Loader abgewiesener relativer Pfad erhält den Status `invalid_path`. In keinem dieser Fälle darf der Graph in das Ranking einfließen.
'''
    if "## 5. Pfad-Sicherheitsgrenze" not in content:
        content = content.rstrip() + section + "\n"
    write(path, content)


def patch_proof() -> None:
    path = "docs/proofs/graph-provenance-coherent-compilation-proof.md"
    content = read(path)
    section = '''

## Retrieval path boundary

An explicitly selected Graph Index is constrained to the SQLite index artifact directory. The query runtime performs only lexical checks on the caller value and passes a filename to the root-bounded loader. This prevents an arbitrary caller-controlled path from reaching the file-open expression while preserving explicit missing-file errors and diagnostic fallback for invalid graph contents.
'''
    if "## Retrieval path boundary" not in content:
        content = content.rstrip() + section + "\n"
    write(path, content)


def patch_test() -> None:
    path = "merger/lenskit/tests/test_graph_rerank.py"
    content = read(path)
    test = '''


def test_graph_path_outside_index_directory_is_rejected(
    mini_index_with_graph,
    tmp_path,
):
    db_path, graph_index_path = mini_index_with_graph
    foreign_dir = tmp_path / "foreign"
    foreign_dir.mkdir()
    foreign_graph = foreign_dir / graph_index_path.name
    foreign_graph.write_text(
        graph_index_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="must share one directory"):
        query_core.execute_query(
            db_path,
            query_text="hello",
            k=10,
            explain=True,
            graph_index_path=foreign_graph,
        )
'''
    if "def test_graph_path_outside_index_directory_is_rejected" not in content:
        content = content.rstrip() + test + "\n"
    write(path, content)


def main() -> None:
    patch_workflow()
    patch_contract()
    patch_proof()
    patch_test()


if __name__ == "__main__":
    main()
