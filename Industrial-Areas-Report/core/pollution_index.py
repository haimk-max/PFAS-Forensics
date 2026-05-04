"""Pollution Index 0-8: logarithmic scale aligned with Water Authority language."""

from __future__ import annotations

from typing import Dict, List, Tuple

_THRESHOLDS: List[Tuple[float, int, str, str]] = [
    # (upper_ratio, index, hebrew, english)
    (0.25,  0, "רקע",              "background"),
    (0.5,   1, "עקבות",            "traces"),
    (1.0,   2, "מתקרב לתקן",      "approaching_standard"),
    (2.0,   3, "חריגה קלה",       "mild_exceedance"),
    (5.0,   4, "חריגה משמעותית",  "significant"),
    (15.0,  5, "זיהום חמור",      "severe"),
    (50.0,  6, "זיהום חמור מאוד", "very_severe"),
    (71.8,  7, "זיהום קיצוני",    "extreme"),
]

_MAX_INDEX = 8
_MAX_HEBREW = "זיהום קריטי"
_MAX_ENGLISH = "critical"


def compute_index(measured: float, standard: float) -> int:
    """Map a single measurement to a 0-8 pollution index.

    ``ratio = measured / standard``; the index is determined by the
    threshold table defined in the project methodology.
    """
    if standard <= 0:
        raise ValueError(f"Standard must be positive, got {standard}")
    if measured < 0:
        return 0
    ratio = measured / standard
    for upper, index, _, _ in _THRESHOLDS:
        if ratio <= upper:
            return index
    return _MAX_INDEX


def compute_group_index(member_indices: Dict[str, int]) -> int:
    """Group index = max of all member indices."""
    if not member_indices:
        return 0
    return max(member_indices.values())


def index_label(index: int, hebrew: bool = True) -> str:
    """Human-readable label for a given index."""
    if index < 0 or index > _MAX_INDEX:
        raise ValueError(f"Index must be 0-{_MAX_INDEX}, got {index}")
    if index == _MAX_INDEX:
        return _MAX_HEBREW if hebrew else _MAX_ENGLISH
    for _, idx, heb, eng in _THRESHOLDS:
        if idx == index:
            return heb if hebrew else eng
    return ""


def ratio_to_percent(measured: float, standard: float) -> float:
    """Return exceedance as percentage of standard."""
    if standard <= 0:
        raise ValueError(f"Standard must be positive, got {standard}")
    return (measured / standard) * 100.0
