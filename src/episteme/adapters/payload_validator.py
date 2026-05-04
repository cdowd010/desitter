"""Dataclass-introspection-based payload validator.

Validates mutation payloads before the gateway constructs domain entities.
Checks that all fields with no default are present in the payload for the
declared resource type.

This validator deliberately does not re-run domain invariant checks — those
are the ``DomainValidator``'s responsibility.  It only catches missing
required fields early, before ``build_entity`` raises a ``TypeError``.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, fields

from ..epistemic.codec import get_entity_class
from ..epistemic.types import Finding, Severity


class SchemaPayloadValidator:
    """``PayloadValidator`` that inspects dataclass field defaults.

    A field is considered *required* when both ``field.default`` and
    ``field.default_factory`` are ``MISSING``.  The validator reports one
    ``CRITICAL`` finding per missing required field.

    An unknown ``resource`` key also produces a single ``CRITICAL`` finding
    rather than raising an exception, so the gateway can surface it as a
    structured result.
    """

    def validate(self, resource: str, payload: Mapping[str, object]) -> list[Finding]:
        """Return findings for any required fields absent from ``payload``.

        Args:
            resource: Canonical resource key (e.g. ``"hypothesis"``).
            payload: Inbound mutation payload to validate.

        Returns:
            list[Finding]: One ``CRITICAL`` finding per required field
                that is missing from the payload.  Empty list means the
                payload passes schema checks.
        """
        try:
            entity_cls = get_entity_class(resource)
        except KeyError:
            return [
                Finding(
                    severity=Severity.CRITICAL,
                    source=f"payload/{resource}",
                    message=f"Unknown resource type: {resource!r}",
                )
            ]

        findings: list[Finding] = []
        for f in fields(entity_cls):  # type: ignore[arg-type]
            required = f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
            if required and f.name not in payload:
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        source=f"payload/{resource}/{f.name}",
                        message=f"Required field {f.name!r} is missing from the payload",
                    )
                )
        return findings
