"""
Path mapping utilities.

CORE RTH often runs inside a Linux container while the indexed assets live on a Windows host.
We keep plugin roots in their original (host) form for stable IDs, but map them to mounted
container paths for filesystem access.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Tuple
import json
import os


def _slash(p: str) -> str:
    return str(p or "").replace("\\", "/")


def _key(p: str) -> str:
    return _slash(p).lower().rstrip("/")


@lru_cache(maxsize=1)
def _load_map() -> List[Tuple[str, str]]:
    """
    Loads mapping from env var `RTH_PATH_MAP_JSON` as a dict:
      {"d:/codex": "/host/codex", ...}

    Returns list of (src_prefix_key, dst_prefix) ordered by descending src length.
    """
    raw = os.getenv("RTH_PATH_MAP_JSON", "") or ""
    raw = raw.strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []

    pairs: List[Tuple[str, str]] = []
    for src, dst in payload.items():
        src_k = _key(str(src))
        dst_s = _slash(str(dst)).rstrip("/")
        if not src_k or not dst_s:
            continue
        pairs.append((src_k, dst_s))

    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def map_path(path: str) -> str:
    """
    Map host paths to container mount paths using prefix replacement.
    If no mapping matches, returns the original path (with slashes normalized).
    """
    p_slash = _slash(path)
    p_key = p_slash.lower()
    for src_k, dst in _load_map():
        if p_key.startswith(src_k):
            rest = p_slash[len(src_k):]
            return (dst + rest) or dst
    return p_slash


def map_env_debug() -> Dict[str, str]:
    """Expose the currently loaded mapping for diagnostics."""
    return {src: dst for src, dst in _load_map()}

