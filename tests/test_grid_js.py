"""static/grid.js in a real browser must match the Python reference (grid.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from grid import latlon_to_maidenhead, maidenhead_to_latlon

STATIC = Path(__file__).resolve().parents[1] / "static"

GRIDS = ["CN85", "CN85pl", "AA00", "RR99", "FN31pr", "JO62", "BL11", "RE78"]
LATLON_POINTS = [
    (45.5, -123.0),
    (0.0, 0.0),
    (-90.0, -180.0),
    (90.0, 180.0),
    (89.999, -179.999),
    (-89.999, 179.999),
    (51.4778, -0.0015),
    (-33.8688, 151.2093),
    (35.6895, 139.6917),
    (64.1466, -21.9426),
    (0.0001, -0.0001),
    (45.479166666666664, -122.70833333333333),
]

GRID_TO_LATLON = """
(arg) => {
  try {
    const result = window.Maidenhead.gridToLatLon(arg);
    return { ok: true, lat: result.lat, lon: result.lon };
  } catch (error) {
    return { ok: false, message: String(error.message || error) };
  }
}
"""

LATLON_TO_GRID = """
(arg) => {
  try {
    return { ok: true, grid: window.Maidenhead.latLonToGrid(arg.lat, arg.lon, arg.precision) };
  } catch (error) {
    return { ok: false, message: String(error.message || error) };
  }
}
"""


@pytest.fixture(scope="module")
def js_page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto("about:blank")
    page.add_script_tag(path=str(STATIC / "grid.js"))
    page.wait_for_function(
        "window.Maidenhead && typeof window.Maidenhead.latLonToGrid === 'function'"
    )
    yield page
    context.close()


@pytest.mark.parametrize("grid", GRIDS)
def test_grid_to_latlon_matches_python(js_page, grid):
    expected_lat, expected_lon = maidenhead_to_latlon(grid)
    result = js_page.evaluate(GRID_TO_LATLON, grid)
    assert result["ok"], result
    assert result["lat"] == pytest.approx(expected_lat, abs=1e-12)
    assert result["lon"] == pytest.approx(expected_lon, abs=1e-12)


@pytest.mark.parametrize("grid", GRIDS)
def test_grid_roundtrip_matches_python(js_page, grid):
    lat, lon = maidenhead_to_latlon(grid)
    result = js_page.evaluate(
        LATLON_TO_GRID, {"lat": lat, "lon": lon, "precision": len(grid)}
    )
    assert result["ok"], result
    assert result["grid"] == grid


@pytest.mark.parametrize(
    "bad", ["CN8", "CN85pl7", "", "CN8-5p", "CN85p_", "RY00", "0N85", "CNX5", None, 42]
)
def test_invalid_grid_throws(js_page, bad):
    result = js_page.evaluate(GRID_TO_LATLON, bad)
    assert result["ok"] is False
    assert result["message"]


@pytest.mark.parametrize(
    "lat,lon",
    [
        (91, 0),
        (-91, 0),
        (0, 181),
        (0, -181),
        ("NaN", 0),
        (0, "Infinity"),
        (None, 0),
        (0, None),
        ("", 0),
        (0, "  "),
        ([], 0),
        (0, []),
    ],
)
def test_invalid_latlon_throws(js_page, lat, lon):
    result = js_page.evaluate(
        LATLON_TO_GRID, {"lat": lat, "lon": lon, "precision": 6}
    )
    assert result["ok"] is False
    assert result["message"]


@pytest.mark.parametrize("precision", [3, 5, 7])
def test_invalid_precision_throws(js_page, precision):
    result = js_page.evaluate(
        LATLON_TO_GRID, {"lat": 0, "lon": 0, "precision": precision}
    )
    assert result["ok"] is False
    assert "precision" in result["message"]


@pytest.mark.parametrize("lat,lon", LATLON_POINTS)
@pytest.mark.parametrize("precision", [4, 6])
def test_latlon_to_grid_matches_python(js_page, lat, lon, precision):
    expected = latlon_to_maidenhead(lat, lon, precision)
    result = js_page.evaluate(
        LATLON_TO_GRID, {"lat": lat, "lon": lon, "precision": precision}
    )
    assert result["ok"], result
    assert result["grid"] == expected


def test_boundary_values_are_clamped_like_python(js_page):
    for lat, lon, expected in (
        (90, 180, "RR99"),
        (-90, -180, "AA00"),
    ):
        result = js_page.evaluate(
            LATLON_TO_GRID, {"lat": lat, "lon": lon, "precision": 4}
        )
        assert result["grid"] == expected


def test_helper_functions(js_page):
    assert js_page.evaluate("window.Maidenhead.isValidGrid('cn85PL')") is True
    assert js_page.evaluate("window.Maidenhead.isValidGrid('CN8')") is False
    assert js_page.evaluate("window.Maidenhead.isValidLatLon(45.5, -123)") is True
    assert js_page.evaluate("window.Maidenhead.isValidLatLon(91, 0)") is False
    assert js_page.evaluate("window.Maidenhead.normalizeGrid(' cn85PL ')") == "CN85pl"
