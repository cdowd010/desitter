"""Built-in gateway metadata catalogs.

These tables centralize the built-in resource and query metadata used by
the gateway without mixing them into gateway orchestration code.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceSpec:
    """Metadata describing how a resource type maps to ``EpistemicGraphPort`` methods.

    The gateway uses this to resolve generic operation names (``register``,
    ``set``, ``transition``) to the concrete method names on the graph
    aggregate and to the attribute name where entities are stored.

    Attributes:
        collection_attr: Name of the ``EpistemicGraphPort`` attribute that
            holds all entities of this type, e.g. ``"hypotheses"``.
        register_method: Method name on ``EpistemicGraphPort`` to call when
            registering a new entity, e.g. ``"register_hypothesis"``.
        update_method: Method name on ``EpistemicGraphPort`` to call when
            updating an existing entity, e.g. ``"update_hypothesis"``.
        transition_method: Method name on ``EpistemicGraphPort`` to call
            when transitioning entity status, e.g. ``"transition_hypothesis"``.
            ``None`` for resource types that do not support status transitions.
    """

    collection_attr: str
    register_method: str
    update_method: str
    transition_method: str | None = None


@dataclass(frozen=True)
class QuerySpec:
    """Metadata describing a named read-only query exposed by the gateway.

    Each entry in ``QUERY_SPECS`` maps a caller-facing query name to the
    concrete ``EpistemicGraphPort`` method that implements it, and declares
    which parameters must be coerced to typed entity IDs before dispatch.

    Attributes:
        method_name: Name of the ``EpistemicGraphPort`` method to call,
            e.g. ``"hypothesis_lineage"``.
        parameter_resources: Mapping of parameter name to resource key
            for parameters that must be coerced to typed IDs before the
            call. For example ``{"cid": "hypothesis"}`` means the ``cid``
            parameter should be coerced to a ``HypothesisId``.
    """

    method_name: str
    parameter_resources: dict[str, str]


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "hypothesis": ResourceSpec("hypotheses", "register_hypothesis", "update_hypothesis", "transition_hypothesis"),
    "assumption": ResourceSpec("assumptions", "register_assumption", "update_assumption"),
    "prediction": ResourceSpec("predictions", "register_prediction", "update_prediction", "transition_prediction"),
    "analysis": ResourceSpec("analyses", "register_analysis", "update_analysis"),
    "objective": ResourceSpec("objectives", "register_objective", "update_objective", "transition_objective"),
    "discovery": ResourceSpec("discoveries", "register_discovery", "update_discovery", "transition_discovery"),
    "dead_end": ResourceSpec("dead_ends", "register_dead_end", "update_dead_end", "transition_dead_end"),
    "parameter": ResourceSpec("parameters", "register_parameter", "update_parameter"),
    "independence_group": ResourceSpec("independence_groups", "register_independence_group", "update_independence_group"),
    "pairwise_separation": ResourceSpec("pairwise_separations", "add_pairwise_separation", "update_pairwise_separation"),
    "observation": ResourceSpec("observations", "register_observation", "update_observation", "transition_observation"),
    "experiment": ResourceSpec("experiments", "register_experiment", "update_experiment", "transition_experiment"),
}
"""Mapping of canonical resource keys to their ``ResourceSpec`` descriptors.

Covers all twelve built-in entity types. The gateway resolves operations
(register, get, list, set, transition) against this table.
"""


QUERY_SPECS: dict[str, QuerySpec] = {
    "hypothesis_lineage": QuerySpec("hypothesis_lineage", {"cid": "hypothesis"}),
    "assumption_lineage": QuerySpec("assumption_lineage", {"cid": "hypothesis"}),
    "prediction_implicit_assumptions": QuerySpec(
        "prediction_implicit_assumptions",
        {"pid": "prediction"},
    ),
    "refutation_impact": QuerySpec("refutation_impact", {"pid": "prediction"}),
    "assumption_support_status": QuerySpec(
        "assumption_support_status",
        {"aid": "assumption"},
    ),
    "predictions_depending_on_hypothesis": QuerySpec(
        "predictions_depending_on_hypothesis",
        {"cid": "hypothesis"},
    ),
    "parameter_impact": QuerySpec("parameter_impact", {"pid": "parameter"}),
}
"""Mapping of query names to their ``QuerySpec`` descriptors.

Each entry declares a named read-only query that the gateway exposes
via ``Gateway.query(query_type, **params)``. Parameters listed in
``QuerySpec.parameter_resources`` are coerced to typed entity IDs
before the underlying graph method is invoked.
"""


__all__ = ["QuerySpec", "RESOURCE_SPECS", "ResourceSpec", "QUERY_SPECS"]