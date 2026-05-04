"""Stable facade for typed client resource helpers.

The helper surface is grouped by resource families so the public client
class can stay stable while the declaration files remain easier to scan.
"""
from __future__ import annotations

from ._hypothesis import _EpistemeClientHypothesisHelpers
from ._registry import _EpistemeClientRegistryHelpers
from ._structure import _EpistemeClientStructureHelpers


class _EpistemeClientResourceHelpers(
    _EpistemeClientHypothesisHelpers,
    _EpistemeClientRegistryHelpers,
    _EpistemeClientStructureHelpers,
):
    """Combined typed helper surface for all built-in client resources.

    Merges the three resource family mixins into one class so that
    ``EpistemeClient`` need only inherit from a single helpers class.
    No new methods are defined here; all implementations live in the
    constituent mixin classes.

    Families:
    - ``_EpistemeClientHypothesisHelpers``: hypotheses, assumptions,
      predictions, analyses, observations, experiments.
    - ``_EpistemeClientRegistryHelpers``: objectives, discoveries, dead ends.
    - ``_EpistemeClientStructureHelpers``: parameters, independence groups,
      pairwise separations.
    """


__all__ = ["_EpistemeClientResourceHelpers"]
