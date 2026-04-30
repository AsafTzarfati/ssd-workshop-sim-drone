import numpy as np

from sim.schema import AnomalyKind, TelemetrySample

KINDS_ROTATION: tuple[AnomalyKind, ...] = (
    "battery_cliff",
    "current_spike",
    "gps_jump",
    "motor_overheat",
    "comm_loss",
    "freefall",
)

_FIB_INTERVALS_S = (1, 1, 2, 3, 5, 8, 13, 21)


def fibonacci_schedule(rate_hz: int = 10) -> list[tuple[int, AnomalyKind]]:
    """Pattern 3 schedule: cumulative Fibonacci seconds × rate_hz, kinds cycling through KINDS_ROTATION."""
    schedule: list[tuple[int, AnomalyKind]] = []
    cumulative = 0
    for i, interval in enumerate(_FIB_INTERVALS_S):
        cumulative += interval
        schedule.append((cumulative * rate_hz, KINDS_ROTATION[i % len(KINDS_ROTATION)]))
    return schedule


class AnomalyInjector:
    def __init__(
        self,
        schedule: list[tuple[int, AnomalyKind]],
        *,
        rate_hz: int = 10,
        seed: int = 0,
    ) -> None:
        self._by_seq: dict[int, AnomalyKind] = dict(schedule)
        self._rate = rate_hz
        self._rng = np.random.default_rng(seed)
        self._battery_offset = 0.0
        self._spike_remaining = 0
        self._overheat_remaining = 0
        self._gps_offset_pending: tuple[float, float] | None = None
        self._comm_loss_remaining = 0
        self._freefall_remaining = 0

    def _trigger(self, kind: AnomalyKind) -> None:
        if kind == "battery_cliff":
            self._battery_offset += 5.0
        elif kind == "current_spike":
            self._spike_remaining = 4
        elif kind == "gps_jump":
            sign_lat = 1 if self._rng.random() < 0.5 else -1
            sign_lon = 1 if self._rng.random() < 0.5 else -1
            self._gps_offset_pending = (sign_lat * 0.001, sign_lon * 0.001)
        elif kind == "motor_overheat":
            self._overheat_remaining = 1
        elif kind == "comm_loss":
            self._comm_loss_remaining = 5 * self._rate
        elif kind == "freefall":
            self._freefall_remaining = self._rate + 2

    def apply(self, sample: TelemetrySample) -> TelemetrySample | None:
        """Mutate sample for active anomaly effects. Returns None when suppressed (comm_loss)."""
        seq = sample["seq"]
        if seq in self._by_seq:
            self._trigger(self._by_seq[seq])

        if self._comm_loss_remaining > 0:
            self._comm_loss_remaining -= 1
            return None

        if self._battery_offset > 0:
            sample["battery_pct"] = max(0.0, sample["battery_pct"] - self._battery_offset)

        if self._spike_remaining > 0:
            sample["current_a"] = 38.0 + float(self._rng.normal(0, 0.5))
            self._spike_remaining -= 1

        if self._overheat_remaining > 0:
            sample["motor_temp_c"] = list(sample["motor_temp_c"])
            sample["motor_temp_c"][0] = 95
            self._overheat_remaining -= 1

        if self._gps_offset_pending is not None:
            d_lat, d_lon = self._gps_offset_pending
            sample["lat"] += d_lat
            sample["lon"] += d_lon
            self._gps_offset_pending = None

        if self._freefall_remaining > 0:
            sample["vertical_speed_mps"] = -10.0 + float(self._rng.normal(0, 0.3))
            self._freefall_remaining -= 1

        return sample
