from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any, Mapping

WINDOW_SIZE = 100

# Fields excluded from the canonical SHA input. `ts` is wall-clock-dependent
# (RealClock vs VirtualClock); `window_sha256` is the field we're populating.
_EXCLUDED_KEYS = frozenset({"ts", "window_sha256"})


class WindowHasher:
    """Rolling SHA-256 over the last N emitted telemetry samples.

    Returns None until the buffer is full. Returns a 64-char hex digest on
    every subsequent update — same digest for the same content regardless
    of whether the run used VirtualClock or RealClock (timestamps excluded).
    """

    def __init__(self, size: int = WINDOW_SIZE) -> None:
        self._size = size
        self._buf: deque[Mapping[str, Any]] = deque(maxlen=size)

    def update(self, sample: Mapping[str, Any]) -> str | None:
        snapshot = {k: v for k, v in sample.items() if k not in _EXCLUDED_KEYS}
        self._buf.append(snapshot)
        if len(self._buf) < self._size:
            return None
        encoded = json.dumps(
            list(self._buf), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
