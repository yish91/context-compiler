from __future__ import annotations

import dataclasses
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def merge_records(
    existing: list[T],
    incoming: list[T],
    key: Callable[[T], Any],
) -> list[T]:
    merged: dict[Any, T] = {}
    for item in existing:
        merged[key(item)] = item
    for item in incoming:
        item_key = key(item)
        current = merged.get(item_key)
        if current is None:
            merged[item_key] = item
        else:
            merged[item_key] = _merge_two(current, item)
    return list(merged.values())


def _merge_two(current: T, incoming: T) -> T:
    return _fill_blank_fields(current, incoming)


def _fill_blank_fields(donor: Any, target: T) -> T:
    updates: dict[str, Any] = {}
    for f in dataclasses.fields(target):
        target_val = getattr(target, f.name)
        donor_val = getattr(donor, f.name)
        if isinstance(target_val, str) and not target_val and donor_val:
            updates[f.name] = donor_val
        elif isinstance(target_val, list) and not target_val and donor_val:
            updates[f.name] = donor_val
    if updates:
        return dataclasses.replace(target, **updates)
    return target


def endpoint_key(item: Any) -> tuple:
    return (item.source_path, item.line, item.method, item.path)


def model_key(item: Any) -> tuple:
    return (item.source_path, item.line, item.name, item.kind)


def component_key(item: Any) -> tuple:
    return (item.source_path, item.line, item.name)


def config_key(item: Any) -> tuple:
    return (item.source_path, item.line, item.name, item.kind)


def entrypoint_key(item: Any) -> tuple:
    return (item.source_path, item.line, item.name, item.kind)
