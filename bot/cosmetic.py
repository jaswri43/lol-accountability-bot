"""Cosmetic, display-only sequential numbering for tasks/task_templates.

The real database id (autoincrementing, never reused) stays the single
source of truth everywhere internally -- foreign keys, button custom_ids,
API route params. This is purely a presentation layer: given the same
ordered list twice, it assigns/resolves 1-indexed positions the same way
both times, but nothing is ever stored. Callers are responsible for
sorting/filtering the list into whatever set and order they want numbered
first -- these functions just enumerate it.
"""

from typing import Sequence, TypeVar

T = TypeVar("T")


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
