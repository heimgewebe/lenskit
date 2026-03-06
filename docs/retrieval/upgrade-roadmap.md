# Upgrade Roadmap: Lenskit als Repository-Kognition-Engine

## Vision & Synthese
Lenskit produziert kanonische, deterministische Artefakte (Markdown, JSON, Retrieval-Index) mit maschinenlesbarer Provenienz. Um epistemische Blindheit (z. B. Bevorzugung sprachlicher Oberflächen bei BM25) zu vermeiden, wird Lenskit um ein **mehrschichtiges, evidenzmarkiertes Architekturmodell** erweitert.

Dieses Modell wird reproduzierbar aus bestehenden Artefakten abgeleitet, per JSON-Schema validiert und im Retrieval direkt verwertet. Die Sichten sind strikt nach Evidenz (statt Scheinpräzision) gegliedert:
- **S0 (belegt):** Struktur, Entrypoints, deklarative Abhängigkeiten, Artefakt-/Contract-Flüsse.
- **S1 (hoch plausibel):** Import-Graph, CLI-Kommandokette, statische Wiring-Heuristiken.
- **S2 (spekulativ):** Laufzeitpfade/Hotspots (nur mit Logs/Tracing).

**Alternative Sinnachse:** Wenn das Ziel nicht „Code finden“, sondern „System steuerbar machen“ ist, wird der Contracts/Flows-Atlas zum primären Graph.

**Priorität:** Implementierung des G0-Graphen (Python-Import-Graph + Entrypoints + Evidenzlabel S0/S1 + Explain) vor Call-Graphen.

## Roadmap in Phasen

Die erwarteten Recall-Gewinne sind plausible Schätzungen.

| Phase | Kernziel | Haupt-Risiko |
|---|---|---|
| P0 | Retrieval „ehrlich & debugbar“ (Explain, Query Router, Eval v2) | Overmatching / falsche Sicherheit |
| P1 | **G0 Graph-Index**: Python Import-Graph + Entrypoints + Evidenzlabel (S0/S1) | Scheinpräzision, Tests verzerren |
| P2 | Graph-aware Scoring: BM25 + Nähe + Entrypoint-Dist + Test-Penalty | Tuning/Tradeoffs |
| P3 | Contracts/Flows-Atlas (Alternative Achse) + CI/Drift Regeln | Governance-Overhead |
| P4 | Multi-Lang Parsing (Tree-sitter) + Symbol-Index v2 | Parser-Wartung |
| P5 | Call-Graph/CPG v2 (S2) | falsch-positive Pfade |

```mermaid
timeline
  title Lenskit Evolution (Roadmap)
  P0 : Explain + Query Router + Eval v2
  P1 : G0 Import-Graph + Entrypoints + Schemas
  P2 : Graph-aware Ranking + Explain-Details
  P3 : Contracts/Flows-Atlas + Drift/CI
  P4 : Tree-sitter Multi-Lang + Symbol-Index
  P5 : Call-Graph/CPG (optional, S2)
```

## Build- und Query-Pipelines

Lenskit nutzt Hash-basierte Provenienz. Die erweiterte Pipeline führt Graph-Index und Entrypoints ein.

```mermaid
flowchart LR
  Repo[Repo scan / merge] --> Dump[dump_index.json]
  Repo --> MD[canonical_md (.md parts)]
  Repo --> Chunks[chunk_index.jsonl]

  Dump -->|canonical_dump_index_sha256| Derived[derived_index.json]
  Chunks --> SQLite[(chunk_index.index.sqlite)]
  Derived --> SQLite

  Chunks --> Arch[architecture.graph.json]
  Chunks --> EP[entrypoints.json]
  Arch --> GIdx[graph_index.json]
  EP --> GIdx

  SQLite --> Query[lenskit query]
  GIdx --> Query
  Query --> Eval[retrieval_eval.json]
```

## Artefakte und Contracts

*Warnung: Die folgenden JSON-Schema Skizzen sind erst verbindliche Contracts, wenn sie als Dateien im designierten Contracts-Bereich des Repositories liegen, validiert werden und Fixtures/Tests existieren. Bis dahin sind es Entwürfe (Drafts).*

**Evidenzlevel Policy (S0/S1/S2)**
Das Evidenzlevel ist ein Pflichtfeld in Graphen. Es gelten folgende Regeln:
- **S0 (belegt):** z. B. CLI-Kommando-Deklarationen.
- **S1 (hoch plausibel):** z. B. statische AST-Imports. **S1 darf nicht als Laufzeitkausalität ausgegeben werden.**
- **S2 (spekulativ):** z. B. Hotspots, Traces.
Die Retrieval-Engine (insb. `--explain`) muss das Evidence-Level jederzeit sichtbar machen, um Scheinpräzision ("der Graph sagt es, also ist es Laufzeit-Wahrheit") zu verhindern.

### architecture.graph.v1 Schema
*Draft sketch – not canonical contract yet.*
*Note: `$id` is a placeholder; final `$id` and path follow repo contract conventions.*
*These schema sketches aim to be compatible with expected repo contract patterns (kind/version/run_id/hash). Finalize once contract location and validator rules are confirmed.*
<!-- TODO: place under <repo canonical contracts path> -->
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "lenskit/schema/architecture.graph.v1.schema.json",
  "title": "Architecture Graph (architecture.graph v1)",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "version", "run_id", "canonical_dump_index_sha256", "nodes", "edges", "coverage"],
  "properties": {
    "kind": { "type": "string", "const": "lenskit.architecture.graph" },
    "version": { "type": "string", "const": "1.0" },
    "run_id": { "type": "string" },
    "canonical_dump_index_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "generated_at": { "type": "string", "format": "date-time" },
    "granularity": { "type": "string", "enum": ["file", "package", "module"] },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["node_id", "kind", "path", "repo", "is_test"],
        "properties": {
          "node_id": { "type": "string" },
          "kind": { "type": "string", "enum": ["file", "package", "module", "external"] },
          "path": { "type": "string" },
          "repo": { "type": "string" },
          "language": { "type": "string" },
          "layer": { "type": "string" },
          "is_test": { "type": "boolean" },
          "size_bytes": { "type": "integer", "minimum": 0 }
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["src", "dst", "edge_type", "evidence", "evidence_level"],
        "properties": {
          "src": { "type": "string" },
          "dst": { "type": "string" },
          "edge_type": { "type": "string", "enum": ["import", "require", "config-link", "string-ref", "call-heuristic"] },
          "evidence_level": { "type": "string", "enum": ["S0", "S1", "S2"] },
          "evidence": {
            "type": "object",
            "additionalProperties": false,
            "required": ["source_path"],
            "properties": {
              "source_path": { "type": "string" },
              "start_line": { "type": "integer", "minimum": 1 },
              "end_line": { "type": "integer", "minimum": 1 },
              "extract": { "type": "string", "maxLength": 240 }
            }
          }
        }
      }
    },
    "coverage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["files_seen", "files_parsed", "edge_counts_by_type", "unknown_layer_share"],
      "properties": {
        "files_seen": { "type": "integer", "minimum": 0 },
        "files_parsed": { "type": "integer", "minimum": 0 },
        "edge_counts_by_type": { "type": "object" },
        "unknown_layer_share": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    }
  }
}
```

### entrypoints.v1 Schema
*Draft sketch – not canonical contract yet.*
*Note: `$id` is a placeholder; final `$id` and path follow repo contract conventions.*
*These schema sketches aim to be compatible with expected repo contract patterns (kind/version/run_id/hash). Finalize once contract location and validator rules are confirmed.*
<!-- TODO: place under <repo canonical contracts path> -->
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "lenskit/schema/entrypoints.v1.schema.json",
  "title": "Entrypoints (entrypoints v1)",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "version", "run_id", "canonical_dump_index_sha256", "entrypoints"],
  "properties": {
    "kind": { "type": "string", "const": "lenskit.entrypoints" },
    "version": { "type": "string", "const": "1.0" },
    "run_id": { "type": "string" },
    "canonical_dump_index_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "entrypoints": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "type", "path", "evidence_level"],
        "properties": {
          "id": { "type": "string" },
          "type": { "type": "string", "enum": ["cli", "module_main", "web", "worker", "test"] },
          "path": { "type": "string" },
          "symbol": { "type": "string" },
          "evidence_level": { "type": "string", "enum": ["S0", "S1", "S2"] },
          "evidence": { "type": "object" }
        }
      }
    }
  }
}
```

### contracts.graph.v1 Schema (Alternative Achse)
*Draft sketch – not canonical contract yet.*
*Note: `$id` is a placeholder; final `$id` and path follow repo contract conventions.*
*These schema sketches aim to be compatible with expected repo contract patterns (kind/version/run_id/hash). Finalize once contract location and validator rules are confirmed.*
<!-- TODO: place under <repo canonical contracts path> -->
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "lenskit/schema/contracts.graph.v1.schema.json",
  "title": "Contracts/Flows Graph (contracts.graph v1)",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "version", "nodes", "edges"],
  "properties": {
    "kind": { "type": "string", "const": "lenskit.contracts.graph" },
    "version": { "type": "string", "const": "1.0" },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "kind"],
        "properties": {
          "id": { "type": "string" },
          "kind": { "type": "string", "enum": ["artifact", "contract", "command", "ci_check"] },
          "schema_id": { "type": "string" }
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["src", "dst", "edge_type", "evidence_level"],
        "properties": {
          "src": { "type": "string" },
          "dst": { "type": "string" },
          "edge_type": { "type": "string", "enum": ["produces", "consumes", "validates", "guards"] },
          "evidence_level": { "type": "string", "enum": ["S0", "S1", "S2"] }
        }
      }
    }
  }
}
```

### Chunk-Metadaten & Range_ref Integration
- **Metadaten-Erweiterung:** `chunk_index.jsonl` erhält optional die Felder `symbol_name`, `node_id`, `entrypoint_distance`, `is_test_penalty`.
- **Proof-Carrying Retrieval (`range_ref`):** Für eine deterministische Extraktion muss der Byte-Range-Bezug zwischen Retrieval-Treffer und Artefaktpfad (`artifact_role = "canonical_md"`) hergestellt werden.
```json
{
  "artifact_role": "canonical_md",
  "repo_id": "example-repo-id",
  "file_path": "lenskit-max-..._merge.md",
  "start_byte": 214998,
  "end_byte": 217441,
  "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "start_line": 1203,
  "end_line": 1321
}
```

## Retrieval-Integration und Explain

### Ranking-Formel
Kombination aus BM25 (FTS5) und Graph-Nähe:
```text
score = w_bm25 * bm25_norm
      + w_graph * graph_proximity
      + w_entry * entrypoint_boost
score = score * test_penalty
```

### Explain Output (Beispiel)
Transparenz über Query-Routing, Gewichte und Treffer-Gründe:
```json
{
  "query": "where does indexing start",
  "router": {
    "intent": "entrypoint",
    "fts_query": "content:(index OR indexing OR build_index) AND path_tokens:(cli OR cmd OR main)",
    "synonyms_used": ["indexing", "build_index"]
  },
  "ranker": {
    "w_bm25": 0.65,
    "w_graph": 0.20,
    "w_entry": 0.15,
    "test_penalty_default": 0.75
  },
  "top_results": [
    {
      "path": "merger/lenskit/cli/main.py",
      "final_score": 0.12,
      "why": ["entrypoint_boost", "near_cli", "not_test"]
    }
  ]
}
```

## Drift Detection und CI-Regeln
- Metriken für den Graph-Index (Zyklen-Count, Anteil unknown layer, Entrypoint-Reachability) dienen als Guardrails.
- Contract-First: Jede neue ArtifactRole erfordert Schema, Beispiel und Test.
- `canonical_dump_index_sha256` Verknüpfung in generierten Graphen (`architecture.graph.json`) muss matchen, ansonsten greift die Stale-Policy.

## Vorschlag für Artefakt-Pfade & Rollen (pending repo conventions)

Artefakte werden stets innerhalb des Bundles (z. B. `_merge.bundle/`) platziert, um Drift zu vermeiden:
- **Rolle im Manifest:** `architecture_graph_json`, `entrypoints_json`, `graph_index_json`.
*(Finalize names once existing manifest role naming is confirmed.)*

## Abhakbare PR-Blaupause (Step-by-Step)

Strategie: Additiv statt brechend (neue Artefakte als roles, Feature Flags). Bei Lenskit ist ein PR erst fertig, wenn **Artefakt + Contract + Test** zusammen laufen.

### PR 1a: Explain Baseline (P0)
**Deliverables:**
- [x] `lenskit query --explain` (immer: FTS_Query + Filter + Top-K Scoring, ohne Router/Rewrite).
- [x] Explain **auch bei 0 Treffern** (mit `why_zero`, z.B. Tokens zu restriktiv).
- [x] Golden Tests: Explain JSON stable prefix order (fts_query, filters) and required keys present.

**Stop-Kriterium:**
- [x] `retrieval_eval` läuft reproduzierbar und liefert für jede Query Explain-Payload (auch im Fail-Fall).

### PR 1b: Query Router MVP (P0)
**Deliverables:**
- [x] `query_router` (Stopwords, Intent Tags, Synonym OR-Expansion).
- [x] Explain Output um Router-Entscheidungen erweitern.

**Bias-Guard:**
- [x] "Overmatching-Schalter": Router kann OR-Expansion über Config abschalten (feature-flagged).

### PR 2: Eval v2 (P0)
**Deliverables:**
- [x] Kategorien im Query-Set (architecture/entrypoint/feature/cli/security).
- [x] Recall@5/10 pro Kategorie.
- [x] Coverage-Metrik (Anteil der Queries mit 0 Treffern).

**Stop-Kriterium:**
- [x] Eval-Output ist schema-validiert + Golden Fixture vorhanden.

### PR 3a: Entrypoints v1 (P1)
*(Minimaler maschinenlesbarer Kern S0)*
**Deliverables:**
- [x] `entrypoints.v1` schema file (path TBD; see Open Questions).
- [x] Entrypoints v1 minimal (console scripts + lenskit cli root).
- [x] CLI: `lenskit architecture --entrypoints` (oder `--format json`).

**Stop-Kriterium:**
- [x] Determinismus: Stabile `node_id` Regeln und sortierte Liste.
- [x] Golden Test: Mini Fixture Project erzeugt exakten Entrypoints Output.

### PR 3b: Import-Graph v1 (P1)
*(Minimaler maschinenlesbarer Kern S1)*
**Deliverables:**
- [x] `architecture.graph.v1` schema file (path TBD; see Open Questions).
- [x] Generator: Python-Imports via AST (Edges: `import`, Evidence S1, line-refs).
- [x] `coverage` vollständig (inklusive `files_parsed / files_seen`) + Warnungen bei low coverage.

**Stop-Kriterium:**
- [x] Determinismus: Sortierte Nodes/Edges.
- [x] Golden Test: Mini Fixture Project erzeugt exakten Graph Output.

### PR 4: graph_index compile + graph-aware rerank (P2)
**Deliverables:**
- [ ] `graph_index.json` (Adjacency + Entrypoint Distances + Metrics).
- [ ] Retrieval: BM25 topN → Rerank (Distance/Entrypoint/Test-Penalty).
- [ ] Explain: Final Score Breakdown + Features per Result.

**Stop-Kriterium:**
- [ ] Rerank ist "feature-flagged" und bietet sauberen Fallback auf BM25.
- [ ] Regression Test: Rerank deterministisch, keine Random Tie Flips.

### PR 5: range_ref (Proof-Carrying Retrieval) (P1/P2)
**Deliverables:**
- [ ] `chunk_index.jsonl` optional erweitert um `content_range_ref` (bundle-konsistent).
- [ ] Query Results können `range_ref` ausgeben.
- [ ] Roundtrip-Test: Top-Result → `range_get` → extrahierter Text matcht Hash.

**Stop-Kriterium:**
- [ ] Eine Retrieval-Antwort ist belegbar (nicht nur plausibel).

---

## Offene Fragen zur Repository-Realität (Open Questions)
*Dieser Abschnitt dient der Klärung von Konventionen, bevor die PRs 3-5 implementiert werden.*

1. **Vertrags-Pfad:** Wo liegt das offizielle `contracts/`-Verzeichnis für die neuen JSON-Schemas (z. B. `architecture.graph.v1.schema.json`) und wo sind die Validatoren angesiedelt?
2. **Artefakt-Rollen:** Entsprechen die neuen Artefakt-Rollen (wie `architecture_graph_json`) den etablierten Konventionen im `bundle.manifest.json`?
3. **Erweiterung von Chunk Index:** Sind Erweiterungen wie `symbol_name`, `node_id` und `is_test_penalty` im aktuellen `chunk_index.jsonl` Schema direkt integrierbar oder verletzen sie Strict-Type Checks?
4. **Schema-Dateinamen/Discovery:** `*.schema.json` vs `*.json` – how does the validator discover and version schemas?
