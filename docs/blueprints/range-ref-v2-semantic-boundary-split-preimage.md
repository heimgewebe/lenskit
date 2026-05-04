# Range-Ref v2 — Semantic Boundary Split (PR Preimage)

## PR-Title

Range-Ref v2 — Semantic Boundary Split

## Ausgangslage

FTS Content Hydration ist im aktuellen Stand bereits umgesetzt und durch Tests plus Laufzeitbeweis bestätigt. Der nächste Schritt ist daher nicht erneute Hydration-Implementierung, sondern die semantische Entwirrung von Range-Referenzen.

## Scope

- Physische Byte-Range von semantischer Claim-/Evidence-Grenze trennen.
- Range-Ref v1 vollständig kompatibel halten.
- Docs-first Contract-Skizze erstellen, bevor Implementierung beginnt.
- Kompatibilität zu bestehendem Resolver sicherstellen (`resolve_range_ref()` bleibt nutzbar).

## Geplante Deliverables (Docs-first)

1. Contract-Skizze für v2 in Architektur-/Contracts-Doku:
   - Klare Achsen: artifact bytes/lines vs. source claim boundary.
   - Semantik pro Feld und Invarianten.
2. Migrations- und Kompatibilitätsnotiz:
   - v1 bleibt lesbar.
   - v2 wird bevorzugtes Zielschema für neue Outputs.
3. Test-Plan (noch ohne Implementierung):
   - Schema-Validation v2.
   - Roundtrip für artifact/source boundary.
   - Backward-Compatibility-Fall v1 -> Resolver.

## Non-Goals

- Kein Agent Reading Pack in diesem PR.
- Kein CI output-health Gate in diesem PR.
- Kein Resolver-Caching in diesem PR (separates Performance-Follow-up).
- Keine Abschwächung bestehender output_health Checks.
- Keine Änderung der bundle-manifest Schema-Semantik in diesem PR.

## Risiken

- Semantische Verwechslung zwischen physischer Position und Claim-Grenze, wenn Feldnamen zu nahe an v1 bleiben.
- Unbeabsichtigter Bruch bestehender Tools, falls v2 ohne Fallback eingeführt wird.

## Guardrails

- v1 bleibt akzeptiert.
- Resolver-Verhalten für v1 bleibt unverändert.
- Jede v2-Erweiterung wird mit expliziter Abbildung auf bestehende Runtime-Felder dokumentiert.
