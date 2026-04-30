from __future__ import annotations

from typing import Callable

import numpy as np

from sim.schema import AnomalyKind, FlightMode

AltProfile = Callable[[int, int], tuple[float, float]]

APOLLO11_PEAK_ALT_M: float = 142.0
APOLLO11_1202_ALARM_T_S: float = 60.0
APOLLO11_MANUAL_TAKEOVER_T_S: float = 110.0
WRIGHT_HOVER_ALT_M: float = 3.0
WRIGHT_HOVER_DURATION_S: float = 10.0


def apollo11_altitude_profile(total_samples: int, rate_hz: int) -> AltProfile:
    f = np.linspace(0.0, 1.0, total_samples)
    alts = APOLLO11_PEAK_ALT_M * (1 - f) ** 2 * (1 + 0.4 * f)
    vspeeds = np.gradient(alts) * rate_hz
    arr_alts = alts
    arr_vspeeds = vspeeds

    def _profile(seq: int, total: int) -> tuple[float, float]:
        return float(arr_alts[seq]), float(arr_vspeeds[seq])

    return _profile


def wright_altitude_profile(total_samples: int, rate_hz: int) -> AltProfile:
    hover_n = int(WRIGHT_HOVER_DURATION_S * rate_hz)
    descent_n = max(1, total_samples - hover_n)
    alts = np.concatenate([
        np.full(hover_n, WRIGHT_HOVER_ALT_M),
        np.linspace(WRIGHT_HOVER_ALT_M, 0.0, descent_n),
    ])
    vspeeds = np.gradient(alts) * rate_hz
    arr_alts = alts
    arr_vspeeds = vspeeds

    def _profile(seq: int, total: int) -> tuple[float, float]:
        i = min(seq, len(arr_alts) - 1)
        return float(arr_alts[i]), float(arr_vspeeds[i])

    return _profile


def apollo11_anomaly_overlay(
    base: list[tuple[int, AnomalyKind]], rate_hz: int
) -> list[tuple[int, AnomalyKind]]:
    alarm_seq = int(APOLLO11_1202_ALARM_T_S * rate_hz)
    out = [s for s in base if s[0] != alarm_seq]
    out.append((alarm_seq, "current_spike"))
    return sorted(out, key=lambda x: x[0])


def apollo11_mode_schedule(rate_hz: int) -> dict[int, FlightMode]:
    return {int(APOLLO11_MANUAL_TAKEOVER_T_S * rate_hz): "MANUAL"}
