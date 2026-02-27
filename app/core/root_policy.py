"""
Root policy helpers.

This is the "Guardian" layer for local roots: what can be treated as a plugin,
what is in-scope for strategic analysis, and how we normalize paths.
"""

from __future__ import annotations

from typing import List, Optional
import json
import os


DEFAULT_STRATEGIC_ROOTS = [
    "c:/users/pc/desktop/biome",
    "d:/codex",
    "d:/simulatore_rcq",
    "d:/core rth",
]


def normalize_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lower().rstrip("/")


def load_strategic_roots() -> List[str]:
    """
    Reads strategic roots from env.

    Supported env vars:
    - RTH_STRATEGIC_ROOTS_JSON='[\"c:/...\",\"d:/...\"]'
    - RTH_STRATEGIC_ROOTS='c:/...,d:/...'
    """
    raw = (os.getenv("RTH_STRATEGIC_ROOTS_JSON") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [normalize_path(x) for x in parsed if str(x).strip()]
        except Exception:
            pass

    raw = (os.getenv("RTH_STRATEGIC_ROOTS") or "").strip()
    if raw:
        return [normalize_path(x) for x in raw.split(",") if str(x).strip()]

    return [normalize_path(x) for x in DEFAULT_STRATEGIC_ROOTS]


def is_within_roots(path: str, roots: Optional[List[str]] = None) -> bool:
    low = normalize_path(path)
    roots = roots or load_strategic_roots()
    for root in roots:
        if low == root or low.startswith(root + "/"):
            return True
    return False


def dedupe_nested_roots(roots: List[str]) -> List[str]:
    """
    Keep only non-overlapping roots (remove nested ones).
    """
    roots_norm = sorted({normalize_path(r) for r in (roots or []) if str(r).strip()}, key=len)
    keep: List[str] = []
    for r in roots_norm:
        if any(r == k or r.startswith(k + "/") for k in keep):
            continue
        keep.append(r)
    return keep

