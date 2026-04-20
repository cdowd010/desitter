"""Control-plane services — mutations and structural queries.

Always available. No feature flags required.
Consumer adapters route through these services.

Modules:
  gateway    — Single mutation/query boundary
  validate   — Graph validation orchestration (read-only)
  check      — Structural diagnostics: ref checks, staleness (read-only, no I/O)
  prose      — Managed-prose sync (I/O via ProseSync collaborator)
  results    — Record analysis results (planned Phase 6)
  export     — Bulk export (read-only)

Dependency rule: controlplane → epistemic. Optional adapters may provide collaborators.
"""
