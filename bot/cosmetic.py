"""Cosmetic, display-only sequential numbering for tasks/task_templates.

The real database id (autoincrementing, never reused) stays the single
source of truth everywhere internally -- foreign keys, button custom_ids,
API route params. This is purely a presentation layer: given the same
ordered list twice, it assigns/resolves 1-indexed positions the same way
both times, but nothing is ever stored. Callers are responsible for
sorting/filtering the list into whatever set and order they want numbered
first -- these functions just enumerate it.
"""

from datetime import datetime
from typing import Protocol, Sequence, TypeVar

T = TypeVar("T")

_SEVERITY_TIER_RANK = {"low": 0, "medium": 1, "high": 2}


class _HasTierAndCreatedAt(Protocol):
    tier: str | None
    created_at: datetime


TT = TypeVar("TT", bound=_HasTierAndCreatedAt)


def sort_by_tier_then_date(items: Sequence[TT]) -> list[TT]:
    """Sorts tasks/task_templates by severity tier (Low, then Medium, then
    High), and within a tier by creation date ascending (oldest first) --
    the shared order /mytasks, /status, and their API/dashboard equivalents
    all display and number by. A missing tier sorts as Low, matching the
    rest of the app's "no tier = behaves like Low" convention (severity.py,
    task_templates' own tier backfill)."""
    return sorted(items, key=lambda item: (_SEVERITY_TIER_RANK.get(item.tier or "low", 0), item.created_at))


def number_items(items: Sequence[T]) -> list[tuple[int, T]]:
    """Pairs each item with a 1-indexed cosmetic position, in the order
    given."""
    return list(enumerate(items, start=1))


def resolve_cosmetic_number(items: Sequence[T], position: int) -> T | None:
    """Given the same ordered list a cosmetic listing was generated from,
    returns the item at that 1-indexed position, or None if out of range."""
    if position < 1 or position > len(items):
        return None
    return items[position - 1]
