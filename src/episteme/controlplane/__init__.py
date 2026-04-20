"""Control-plane services. Mutations and structural queries.

Always available. No feature flags required.
Consumer adapters route through these services.

Modules:
  gateway: single mutation/query boundary
  validate: graph validation orchestration (read-only)
  check: structural diagnostics: ref checks, staleness (read-only, no I/O)
  prose: managed-prose sync (I/O via ProseSync collaborator)
  results: record analysis results (planned Phase 6)
  export: bulk export (read-only)

Dependency rule: controlplane → epistemic. Optional adapters may provide collaborators.
"""
