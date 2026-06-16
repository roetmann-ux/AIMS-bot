"""In-process guardrails for the hosted/public deployment.

A public link that runs live scoring on the operator's central API keys must be bounded, or anyone
with the URL could run up a bill. This adds a global live-spend ceiling and a per-visitor hourly
rate limit. In-memory (fine for a single instance); both are no-ops unless configured.
"""
from __future__ import annotations

import threading
import time

import config

_lock = threading.Lock()
_spend = 0.0
_hits: dict[str, list[float]] = {}


def spent() -> float:
    return round(_spend, 2)


def remaining_usd() -> float:
    if not config.GLOBAL_CAP_USD:
        return float("inf")
    return max(0.0, round(config.GLOBAL_CAP_USD - _spend, 2))


def charge(usd: float) -> bool:
    """Reserve `usd` against the global cap. Returns False (and reserves nothing) if it would exceed."""
    global _spend
    with _lock:
        if config.GLOBAL_CAP_USD and _spend + usd > config.GLOBAL_CAP_USD:
            return False
        _spend += usd
        return True


def rate_ok(key: str, limit: int | None = None, window: int = 3600) -> bool:
    """True if `key` (e.g. visitor IP) is under `limit` actions in the last `window` seconds."""
    limit = config.RATE_LIMIT_PER_HOUR if limit is None else limit
    if not limit:
        return True
    now = time.time()
    with _lock:
        xs = [t for t in _hits.get(key, []) if now - t < window]
        if len(xs) >= limit:
            _hits[key] = xs
            return False
        xs.append(now)
        _hits[key] = xs
        return True
