import math

_DEFAULT_ORIGIN = (31.7683, 35.2137)
_M_PER_DEG_LAT = 111_320.0


def _meters_to_latlon(
    origin: tuple[float, float], dx_m: float, dy_m: float
) -> tuple[float, float]:
    lat0, lon0 = origin
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return (lat0 + dy_m / _M_PER_DEG_LAT, lon0 + dx_m / m_per_deg_lon)


def israeli_flag(
    origin: tuple[float, float] = _DEFAULT_ORIGIN,
) -> list[tuple[float, float]]:
    """Closed polygon: two horizontal stripes + Star of David, ~500m × 333m bbox."""
    pts_m: list[tuple[float, float]] = []

    def _trace(corners: list[tuple[float, float]], n_per_edge: int = 4) -> None:
        closed = list(corners) + [corners[0]]
        for a, b in zip(closed, closed[1:]):
            for i in range(n_per_edge):
                t = i / n_per_edge
                pts_m.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))

    # Top stripe (thin band near top of bbox, y ∈ [120, 145])
    _trace([(-250, 120), (250, 120), (250, 145), (-250, 145)])
    # Bottom stripe (thin band near bottom of bbox, y ∈ [-145, -120])
    _trace([(-250, -145), (250, -145), (250, -120), (-250, -120)])

    # Star of David: two equilateral triangles, side 140m, centered on origin
    side = 140.0
    h = side * math.sqrt(3) / 2
    up = [(0.0, h * 2 / 3), (-side / 2, -h / 3), (side / 2, -h / 3)]
    down = [(0.0, -h * 2 / 3), (-side / 2, h / 3), (side / 2, h / 3)]
    _trace(up)
    _trace(down)

    pts_m.append(pts_m[0])  # close the polygon

    return [_meters_to_latlon(origin, x, y) for x, y in pts_m]


def heart(
    origin: tuple[float, float] = _DEFAULT_ORIGIN,
    n: int = 60,
) -> list[tuple[float, float]]:
    """Parametric heart curve, ~400m wide, naturally closed."""
    scale = 400.0 / 32.0
    pts_m: list[tuple[float, float]] = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = (
            13 * math.cos(t)
            - 5 * math.cos(2 * t)
            - 2 * math.cos(3 * t)
            - math.cos(4 * t)
        )
        pts_m.append((x * scale, y * scale))
    pts_m.append(pts_m[0])

    return [_meters_to_latlon(origin, x, y) for x, y in pts_m]
