# Lens Card Compact Density v1 Proof

Bureau task: `RPU-V1-T018`.

The opt-in `compact` collection density removes only repeated per-card `does_not_establish` arrays. The complete mandatory negative-semantics tuple remains once at collection level. The default `verbose` mode preserves self-contained cards.

The new `produce_lens_card_collection()` helper is an in-memory consumer projection. It does not register a bundle artifact or replace the canonical single-card schema. The established `produce_lens_card()` and `produce_lens_cards()` APIs and their default outputs remain unchanged.

Representative deterministic JSON measurement for three cards:

- verbose bytes: 1799
- compact bytes: 1274
- saved bytes: 525
- reduction: 29.2%

The measurement establishes serialization-size reduction for the named fixture only. It does not establish runtime correctness, general token savings, test sufficiency, agent-quality improvement, or merge readiness.
