"""Domain exception hierarchy for the epistemic kernel.

These exceptions are domain vocabulary: they describe what can go
wrong in terms the domain understands (duplicate IDs, broken
references, cycles, invariant violations). They are independent of
the aggregate implementation and may be caught anywhere in the
system without pulling in the full EpistemicGraph module.
"""
from __future__ import annotations


class EpistemicError(Exception):
    """Base exception for all domain errors in the epistemic kernel.

    All exceptions raised by the EpistemicGraph inherit from this class,
    making it easy for callers to catch any domain error with a single
    handler.
    """


class DuplicateIdError(EpistemicError):
    """Raised when registering an entity whose ID already exists in the graph.

    Each entity type has a unique namespace. A hypothesis ID only needs to be
    unique among hypotheses, not across all entity types.
    """

    pass


class BrokenReferenceError(EpistemicError):
    """Raised when an operation references an entity ID that does not exist.

    Also raised when a safe-deletion check finds that other entities
    still hold hard references to the entity being removed.
    """

    pass


class CycleError(EpistemicError):
    """Raised when a graph mutation would introduce a dependency cycle.

    The ``depends_on`` graphs for both hypotheses and assumptions must
    remain acyclic (DAG). This error is raised during registration
    or update if adding the new edges would violate that constraint.
    """

    pass


class InvariantViolation(EpistemicError):
    """Raised when post-conditions or global domain invariants are violated.

    Used for programmatic invariant checks that are not tied to a
    specific entity operation but represent a broader structural
    integrity failure.
    """

    pass


__all__ = [
    "BrokenReferenceError",
    "CycleError",
    "DuplicateIdError",
    "EpistemicError",
    "InvariantViolation",
]
