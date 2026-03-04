# lenskit – Index

Kurzüberblick über Ordner:
- `scripts/` – wiederverwendbare Helfer
- `merger/lenskit/` – **repoLens** (Primary Tool) – erzeugt strukturierte Merge-Berichte für KIs.
- `merger/repomerger/` – Legacy-Merger (Standalone).

## Nutzung (Beispiele)

### repoLens (Empfohlen)

Das Hauptwerkzeug, um Repositories für LLMs aufzubereiten.

```bash
# Overview
python3 -m merger.lenskit.cli.rlens . --level overview

# Full Merge mit Split (20MB) und Meta-Drosselung
python3 -m merger.lenskit.cli.rlens . --level max --split-size 20MB --meta-density standard
```

Siehe [merger/lenskit/repoLens-spec.md](merger/lenskit/repoLens-spec.md) für Details.

### JSONL Tools

Minimale Befehle, um die verfügbaren Werkzeuge aufzurufen:

```bash
bash scripts/jsonl-validate.sh --help
bash scripts/jsonl-tail.sh --help
```

- `scripts/jsonl-validate.sh` – prüft NDJSON (eine JSON-Entität pro Zeile) gegen ein JSON-Schema (AJV v5).
- `scripts/jsonl-tail.sh`
- `scripts/jsonl-compact.sh`

## Organismus-Kontext

Dieses Repository ist Teil des **Heimgewebe-Organismus**.

Rolle dieses Repos im Organismus: **Merger**, **Scanner** und epistemischer Kern
für strukturierte Repository-Aufbereitung.

Die übergeordnete Architektur, Achsen, Rollen und Contracts sind zentral beschrieben im  
👉 [`metarepo/docs/heimgewebe-organismus.md`](https://github.com/heimgewebe/metarepo/blob/main/docs/heimgewebe-organismus.md)  
👉 [`metarepo/docs/heimgewebe-zielbild.md`](https://github.com/heimgewebe/metarepo/blob/main/docs/heimgewebe-zielbild.md).

Alle Rollen-Definitionen, Datenflüsse und Contract-Zuordnungen dieses Repos
sind dort verankert.

### Merge Job Deduplication

When requesting a non-plan repository merge via the WebUI, the JSON payload includes `force_new: true` to ensure a fresh merge is executed rather than reusing a cached job. Plan-only jobs omit the `force_new` flag so they can reuse cached planning results when possible.
