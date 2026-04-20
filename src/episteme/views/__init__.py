"""View services — composed summaries and derived read models.

Always available. No feature flags required.
Compose core service outputs into holistic reports or derived summaries.
Views are read-only.

Modules:
  health   — Composed health report (aggregates validate + check)
  status   — Summary read model for dashboard display
  metrics  — Evidence statistics (tier A summary, correlation-aware counts)
  evidence — Per-hypothesis evidence summary (predictions, assumptions, staleness)

Dependency rule: views → controlplane and epistemic. Never → concrete deployment adapters.
"""
