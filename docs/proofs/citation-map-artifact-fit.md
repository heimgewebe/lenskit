# Citation Map Artifact Fit

## Zweck

Klärt, welche vorhandenen Artefakte eine spätere `citation_map_jsonl` nutzen darf und
welche Rollen sie nicht übernehmen darf.

## Belegter Ist-Zustand

- `canonical_md` ist Inhaltsträger und kanonische Vollquelle.
- `chunk_index_jsonl` ist abgeleiteter Retrieval-Index.
- `bundle_manifest` ist die stärkste Registry-Basis.
- `dump_index_json` ist Navigation/View.
- `derived_manifest_json` ist Derived-/Cache-View.
- `sqlite_index` ist Runtime-Cache.
- `citation_map_jsonl` ist geplant, aber noch nicht implementiert.

## Entscheidung

`citation_map_jsonl` wird später ein neues abgeleitetes Belegadress-Artefakt.

Sie ersetzt nicht:

- `canonical_md`
- `chunk_index_jsonl`
- `range-ref.v1`
- `sqlite_index`
- `bundle_manifest`

## Geplante Rolle

`citation_map_jsonl` darf später nur:

- `authority: navigation_index`
- `canonicality: derived`

Sie darf nie behaupten:

- `canonical_content`
- `content_source`
- `runtime_cache`

## Inputs für spätere Citation Map

- `canonical_md`
- `chunk_index_jsonl`
- `bundle_manifest`

## Nicht voraussetzen

- Inline-`content` im Chunk ist nicht Pflicht.
- SQLite ist keine Citation-Wahrheit.
- `source_range.status = exact` ist nicht garantiert.
- Query-Ergebnisse dürfen Citations später referenzieren, aber nicht selbst erzeugen.
- Evidence Use / Claim-Bewertung gehört nicht in Citation Map v1.

## Offene Folge-PRs

1. `citation-map.v1.schema.json`
2. Minimale Beispiele
3. Schema-Test
4. Bundle-Manifest-Role `citation_map_jsonl`
5. Chunk-Index dual range
6. Citation-Map-Producer
7. Citation-/Evidence-Health-Prüfung
8. Real-Dump-Proof

## Stop-Kriterium für diesen Proof

Der Proof ist ausreichend, wenn klar ist:

- Welche Artefakte genutzt werden.
- Welche Artefakte nicht ersetzt werden.
- Welche Semantik vor Contract/Producer geklärt sein muss.
