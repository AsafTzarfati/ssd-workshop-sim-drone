import math

from sim.paths import heart, israeli_flag

_M_PER_DEG_LAT = 111_320.0


def _bbox_meters(pts: list[tuple[float, float]]) -> tuple[float, float]:
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    lat0 = sum(lats) / len(lats)
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat0))
    height_m = (max(lats) - min(lats)) * _M_PER_DEG_LAT
    width_m = (max(lons) - min(lons)) * m_per_deg_lon
    return (width_m, height_m)


def test_israeli_flag_is_closed_polygon():
    pts = israeli_flag()
    assert pts[0] == pts[-1]
    assert len(pts) >= 20


def test_israeli_flag_bounding_box():
    pts = israeli_flag()
    width_m, height_m = _bbox_meters(pts)
    assert 450 < width_m < 550, f"width {width_m:.1f}"
    assert 280 < height_m < 350, f"height {height_m:.1f}"


def test_heart_is_closed():
    pts = heart()
    assert pts[0] == pts[-1]
    assert len(pts) >= 30


def test_paths_use_origin():
    origin = (32.0, 35.0)
    for pts in (israeli_flag(origin=origin), heart(origin=origin)):
        avg_lat = sum(p[0] for p in pts) / len(pts)
        avg_lon = sum(p[1] for p in pts) / len(pts)
        assert abs(avg_lat - origin[0]) < 0.01
        assert abs(avg_lon - origin[1]) < 0.01
