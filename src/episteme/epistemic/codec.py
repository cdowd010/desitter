"""Shared conversion helpers for domain entities.

This module owns the translation between:
  - typed domain dataclasses
  - primitive payload dictionaries used by the gateway
    - primitive transport values exchanged at system boundaries

It contains no I/O and no business rules.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum
import types
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from .model import (
    Analysis,
    Assumption,
    Experiment,
    Hypothesis,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Objective,
)


ENTITY_TYPES: dict[str, type[object]] = {
    "hypothesis": Hypothesis,
    "assumption": Assumption,
    "prediction": Prediction,
    "analysis": Analysis,
    "objective": Objective,
    "discovery": Discovery,
    "dead_end": DeadEnd,
    "parameter": Parameter,
    "independence_group": IndependenceGroup,
    "pairwise_separation": PairwiseSeparation,
    "observation": Observation,
    "experiment": Experiment,
}
"""Mapping of canonical resource keys to their dataclass types.

Used by codec functions and the payload validator to resolve resource
names to model classes.
"""


def get_entity_class(resource: str) -> type[object]:
    """Return the model dataclass for a canonical resource name.

    Args:
        resource: A canonical resource key such as ``"hypothesis"``,
            ``"prediction"``, or ``"independence_group"``.

    Returns:
        type[object]: The corresponding dataclass type (e.g.
            ``Hypothesis``, ``Prediction``).

    Raises:
        KeyError: If ``resource`` is not a recognized resource key.
    """
    try:
        return ENTITY_TYPES[resource]
    except KeyError as exc:
        raise KeyError(f"Unsupported resource type: {resource!r}") from exc


def entity_id_type(resource: str) -> object:
    """Return the NewType constructor for a resource's identifier field.

    Inspects the ``id`` field's type annotation on the model dataclass
    for the given resource and returns the NewType callable.

    Args:
        resource: A canonical resource key (e.g. ``"hypothesis"``).

    Returns:
        object: The NewType constructor (e.g. ``HypothesisId``) that can
            be called with a string to produce a typed identifier.

    Raises:
        KeyError: If ``resource`` is not a recognized resource key.
    """
    entity_cls = get_entity_class(resource)
    return get_type_hints(entity_cls)["id"]


def status_enum_type(resource: str) -> type[Enum] | None:
    """Return the status Enum class for a resource, if one is defined.

    Checks whether the model dataclass for the given resource has a
    ``status`` field annotated with an ``Enum`` subclass.

    Args:
        resource: A canonical resource key (e.g. ``"prediction"``).

    Returns:
        type[Enum] | None: The status enum class (e.g.
            ``PredictionStatus``), or ``None`` if the resource does
            not have a status field.

    Raises:
        KeyError: If ``resource`` is not a recognized resource key.
    """
    entity_cls = get_entity_class(resource)
    annotation = get_type_hints(entity_cls).get("status")
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    return None


def normalize_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Convert mixed Python values to primitive transport values.

    Recursively serializes all values in the payload: enums become
    their ``.value``, dates become ISO strings, sets become sorted
    lists, and dataclass instances become dicts.

    Args:
        payload: A mapping of field names to Python values, possibly
            containing enums, dates, sets, or nested dataclasses.

    Returns:
        dict[str, object]: A new dictionary with all keys converted
            to strings and all values serialized to transport-friendly
            primitives.
    """
    return {str(key): serialize_value(value) for key, value in payload.items()}


def build_entity(resource: str, payload: Mapping[str, object]) -> object:
    """Construct a typed domain entity from a primitive payload mapping.

    Normalizes the payload, then coerces each field value to the type
    declared by the entity's dataclass annotations (e.g. strings to
    enums, lists to sets, ISO date strings to ``date`` objects).

    Args:
        resource: A canonical resource key (e.g. ``"hypothesis"``).
        payload: A mapping of field names to primitive values. Fields
            not present in the payload are omitted from construction
            and must have defaults on the dataclass.

    Returns:
        object: A fully constructed dataclass instance of the
            appropriate entity type.

    Raises:
        KeyError: If ``resource`` is not a recognized resource key.
        TypeError: If a field value cannot be coerced to its annotated type.
        ValueError: If an enum value string does not match any member.
    """
    entity_cls = get_entity_class(resource)
    type_hints = get_type_hints(entity_cls)
    normalized = normalize_payload(payload)
    kwargs: dict[str, object] = {}

    for field in fields(entity_cls):
        if field.name not in normalized:
            continue
        kwargs[field.name] = _coerce_value(normalized[field.name], type_hints[field.name])

    return entity_cls(**kwargs)


def deserialize_entity(resource: str, payload: Mapping[str, object]) -> object:
    """Construct a typed domain entity from a primitive payload.

    This is an alias for ``build_entity`` used when decoding gateway
    responses back into typed domain objects on the client side.

    Args:
        resource: A canonical resource key (e.g. ``"hypothesis"``).
        payload: A mapping of field names to primitive values.

    Returns:
        object: A fully constructed dataclass instance.
    """
    return build_entity(resource, payload)


def serialize_value(value: object) -> object:
    """Recursively serialize a Python value to primitive transport values.

    Handles dataclass instances, enums, dates, sets, lists, tuples,
    and dicts. Sets are converted to sorted lists for deterministic
    output. Dict keys are sorted alphabetically.

    Args:
        value: Any Python value to serialize.

    Returns:
        object: A transport-friendly primitive (str, int, float, bool,
            None, list, or dict).
    """
    if is_dataclass(value) and not isinstance(value, type):
        return entity_to_dict(value)

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, set):
        serialized = [serialize_value(item) for item in value]
        return sorted(serialized, key=_sort_key)

    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda item: str(item[0]))
        return {
            str(serialize_value(key)): serialize_value(item_value)
            for key, item_value in items
        }

    return value


def entity_to_dict(entity: object) -> dict[str, object]:
    """Serialize a domain dataclass instance to a primitive payload mapping.

    Each field on the dataclass is serialized via ``serialize_value``.
    The result is a flat mapping suitable for boundary transport.

    Args:
        entity: A dataclass instance to serialize. Must be an instance,
            not a class.

    Returns:
        dict[str, object]: A mapping of ``{field_name: serialized_value}``
            for every field on the dataclass.

    Raises:
        TypeError: If ``entity`` is not a dataclass instance.
    """
    if not is_dataclass(entity) or isinstance(entity, type):
        raise TypeError(f"Expected dataclass instance, got {type(entity)!r}")

    return {
        field.name: serialize_value(getattr(entity, field.name))
        for field in fields(entity)
    }


def _coerce_value(value: object, annotation: object) -> object:
    """Coerce a primitive value to the type declared by a dataclass annotation.

    Handles NewType wrappers, Optional/Union types, sets, lists, dicts,
    dates, enums, and primitive types. Recursively coerces container
    contents.

    Args:
        value: The raw value from a deserialized payload.
        annotation: The type annotation from the dataclass field.

    Returns:
        object: The value coerced to the target type.

    Raises:
        TypeError: If the value's structure is incompatible with the
            annotation (e.g. a string where an iterable is expected).
        ValueError: If coercion fails (e.g. an invalid enum member
            string).
    """
    if annotation in (Any, object):
        return value

    if value is None:
        return None

    if hasattr(annotation, "__supertype__"):
        supertype = annotation.__supertype__
        return annotation(_coerce_value(value, supertype))

    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_none_args = [arg for arg in get_args(annotation) if arg is not type(None)]
        for arg in non_none_args:
            try:
                return _coerce_value(value, arg)
            except (TypeError, ValueError):
                continue
        raise ValueError(f"Cannot coerce {value!r} to {annotation!r}")

    if origin in (set, frozenset):
        item_type = get_args(annotation)[0]
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise TypeError(f"Expected iterable for {annotation!r}, got {type(value)!r}")
        return set(_coerce_value(item, item_type) for item in value)

    if origin is list:
        item_type = get_args(annotation)[0]
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise TypeError(f"Expected iterable for {annotation!r}, got {type(value)!r}")
        return [_coerce_value(item, item_type) for item in value]

    if origin is dict:
        key_type, value_type = get_args(annotation)
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected mapping for {annotation!r}, got {type(value)!r}")
        return {
            _coerce_value(key, key_type): _coerce_value(item_value, value_type)
            for key, item_value in value.items()
        }

    if annotation is date:
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise TypeError(f"Expected ISO date string, got {type(value)!r}")
        return date.fromisoformat(value)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if isinstance(value, annotation):
            return value
        return annotation(value)

    if annotation in (str, int, float, bool):
        if isinstance(value, annotation):
            return value
        return annotation(value)

    return value


def _sort_key(value: object) -> str:
    """Return a string sort key for arbitrary serialized values.

    Used to produce deterministic ordering of set elements and
    dictionary keys during serialization.

    Args:
        value: Any serialized value.

    Returns:
        str: The ``repr()`` of the value, suitable for lexicographic
            sorting.
    """
    return repr(value)