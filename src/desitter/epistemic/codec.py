"""Shared conversion helpers for domain entities.

This module owns the translation between:
  - typed domain dataclasses
  - primitive payload dictionaries used by the gateway
  - JSON-friendly values written by the repository

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
    Claim,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)


ENTITY_TYPES: dict[str, type[object]] = {
    "claim": Claim,
    "assumption": Assumption,
    "prediction": Prediction,
    "analysis": Analysis,
    "theory": Theory,
    "discovery": Discovery,
    "dead_end": DeadEnd,
    "parameter": Parameter,
    "independence_group": IndependenceGroup,
    "pairwise_separation": PairwiseSeparation,
}


def get_entity_class(resource: str) -> type[object]:
    """Return the model class for a canonical resource name."""
    try:
        return ENTITY_TYPES[resource]
    except KeyError as exc:
        raise KeyError(f"Unsupported resource type: {resource!r}") from exc


def entity_id_type(resource: str) -> object:
    """Return the NewType constructor for a resource identifier."""
    entity_cls = get_entity_class(resource)
    return get_type_hints(entity_cls)["id"]


def status_enum_type(resource: str) -> type[Enum] | None:
    """Return the status enum for a resource, if the model defines one."""
    entity_cls = get_entity_class(resource)
    annotation = get_type_hints(entity_cls).get("status")
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    return None


def normalize_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Convert mixed Python values to JSON-friendly primitives."""
    return {str(key): serialize_value(value) for key, value in payload.items()}


def build_entity(resource: str, payload: Mapping[str, object]) -> object:
    """Construct a typed domain entity from a primitive payload mapping."""
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
    """Alias for build_entity used when decoding gateway responses."""
    return build_entity(resource, payload)


def serialize_value(value: object) -> object:
    """Recursively serialize a Python value to JSON-friendly primitives."""
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
    """Serialize a domain dataclass to a JSON-friendly dictionary."""
    if not is_dataclass(entity) or isinstance(entity, type):
        raise TypeError(f"Expected dataclass instance, got {type(entity)!r}")

    return {
        field.name: serialize_value(getattr(entity, field.name))
        for field in fields(entity)
    }


def _coerce_value(value: object, annotation: object) -> object:
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
    return repr(value)