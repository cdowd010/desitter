"""Read-only structural diagnostics.

Pure functions that inspect the epistemic graph and return findings without
mutating state or performing I/O. Managed-prose operations (which carry
a filesystem collaborator) live in ``prose.py``.
"""
from __future__ import annotations

from ..epistemic.ports import EpistemicGraphPort
from ..epistemic.types import Finding, Severity


# ── Diagnostics ──────────────────────────────────────────────────


def check_refs(
    graph: EpistemicGraphPort,
) -> list[Finding]:
    """Verify all cross-references in the epistemic graph are consistent.

    Checks that every ID reference in the graph (e.g. ``Hypothesis.assumptions``,
    ``Prediction.hypotheses``) points to an existing entity.

    Args:
        graph: The epistemic graph to check.

    Returns:
        list[Finding]: Findings for any broken references.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def check_stale(
    graph: EpistemicGraphPort,
) -> list[Finding]:
    """Identify analyses that should be reviewed after parameter changes.

    Compares each parameter's ``last_modified`` date against the
    ``last_result_date`` of analyses that depend on it. When a parameter
    was modified after an analysis's last recorded run, that analysis
    (and its downstream predictions) may be stale.

    Also reports analyses that have never been run (``last_result_date``
    is None) but have parameters with a ``last_modified`` date.

    For each stale analysis, computes the blast radius via
    ``parameter_impact`` and includes affected predictions in the finding.

    Args:
        graph: The epistemic graph to check.

    Returns:
        list[Finding]: WARNING findings for stale analyses and their
            downstream predictions.
    """
    findings: list[Finding] = []
    # Build reverse index: analysis → set of stale parameter IDs
    stale_params_by_analysis: dict[str, set[str]] = {}

    for par_id, param in graph.parameters.items():
        if param.last_modified is None:
            continue
        for an_id in param.used_in_analyses:
            analysis = graph.analyses.get(an_id)
            if analysis is None:
                continue
            if analysis.last_result_date is None:
                # Never run, but parameter has a modification date
                stale_params_by_analysis.setdefault(an_id, set()).add(par_id)
            elif param.last_modified > analysis.last_result_date:
                stale_params_by_analysis.setdefault(an_id, set()).add(par_id)

    for an_id, stale_pars in stale_params_by_analysis.items():
        analysis = graph.analyses.get(an_id)
        if analysis is None:
            continue
        # Find downstream predictions linked to this analysis
        affected_predictions = {
            pid for pid, pred in graph.predictions.items()
            if an_id in pred.analyses
        }
        # Also find predictions via hypotheses covered by this analysis
        for cid in analysis.hypotheses_covered:
            affected_predictions.update(graph.predictions_depending_on_hypothesis(cid))

        msg = (
            f"Analysis {an_id} may be stale: parameter(s) "
            f"{sorted(stale_pars)} modified after last run"
        )
        if analysis.last_result_date is None:
            msg = (
                f"Analysis {an_id} has never been run but depends on "
                f"parameter(s) {sorted(stale_pars)} with recorded modifications"
            )
        if affected_predictions:
            msg += f". Affected predictions: {sorted(affected_predictions)}"

        findings.append(Finding(
            Severity.WARNING,
            f"analyses/{an_id}",
            msg,
        ))

    return findings


__all__ = ["check_refs", "check_stale"]
