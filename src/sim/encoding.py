from __future__ import annotations

HIDDEN_MESSAGE = "HELLO COPILOT"
MAINT_INTERVAL_S = 30.0
MAINT_WINDOW_SAMPLES = 10

_SPACE_SUBSTITUTE = ord("_")  # 95 — space (32) is outside [65,122]; substitute with '_'


def encode(message: str) -> list[int]:
    """Return ASCII ints for each char in *message*.

    Spaces are substituted with '_' (95) so every value stays within the
    printable-letter range [65, 122] used by Pattern 5.
    """
    result: list[int] = []
    for ch in message:
        v = _SPACE_SUBSTITUTE if ch == " " else ord(ch)
        if not (65 <= v <= 122):
            raise ValueError(f"Character {ch!r} encodes to {v}, outside [65, 122]")
        result.append(v)
    return result


def decode(values: list[int]) -> str:
    """Return the string represented by a list of ASCII ints."""
    return "".join(chr(v) for v in values)
