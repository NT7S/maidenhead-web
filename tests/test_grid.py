import math
import pytest

from grid import latlon_to_maidenhead, maidenhead_to_latlon


def test_cn85_center():
    assert maidenhead_to_latlon("CN85") == pytest.approx((45.5, -123.0))


def test_cn85pl_center():
    # CN85 is 45..46 N, 124..122 W. Subsquare p is 15 * 5' east of 124 W,
    # and l is 11 * 2.5' north of 45 N. Add half a subsquare for the center.
    assert maidenhead_to_latlon("CN85pl") == pytest.approx(
        (45.479166666666664, -122.70833333333333)
    )


@pytest.mark.parametrize("grid", ["CN85", "CN85pl", "AA00", "RR99", "FN31pr"])
def test_grid_roundtrip(grid):
    lat, lon = maidenhead_to_latlon(grid)
    assert latlon_to_maidenhead(lat, lon, precision=len(grid)) == grid


@pytest.mark.parametrize(
    "bad",
    ["CN8", "CN85pl7", "", "CN8-5p", "CN85p_", "RY00", "0N85", "CNX5"],
)
def test_invalid_grid(bad):
    with pytest.raises(ValueError):
        maidenhead_to_latlon(bad)


@pytest.mark.parametrize(
    "lat,lon",
    [(91, 0), (-91, 0), (0, 181), (0, -181), (math.nan, 0), (0, math.inf)],
)
def test_invalid_latlon(lat, lon):
    with pytest.raises(ValueError):
        latlon_to_maidenhead(lat, lon)


@pytest.mark.parametrize("precision", [3, 5, 7])
def test_invalid_precision(precision):
    with pytest.raises(ValueError):
        latlon_to_maidenhead(0, 0, precision=precision)


def test_boundary_latlon_to_grid():
    assert latlon_to_maidenhead(90, 180, precision=4) == "RR99"
    assert latlon_to_maidenhead(-90, -180, precision=4) == "AA00"
