"""Maidenhead grid locator conversions.

A locator is built from:
  1. two field letters A-R (18 columns/rows, 20 deg lon x 10 deg lat)
  2. two square digits 0-9 (2 deg lon x 1 deg lat)
  3. optionally two subsquare letters A-X (5 min lon x 2.5 min lat)

`maidenhead_to_latlon` returns the center of the square.  `latlon_to_maidenhead`
uses floor semantics at cell boundaries and clamps the exact +90/+180 edge to
the last valid cell.
"""

from __future__ import annotations

import math


def _letter_index(ch: str, last: str) -> int:
    value = ord(ch) - ord("A")
    if not 0 <= value <= ord(last) - ord("A"):
        raise ValueError(f"invalid letter {ch!r}")
    return value


def maidenhead_to_latlon(grid: str) -> tuple[float, float]:
    """Return (latitude, longitude) of the center of a 4- or 6-char locator."""
    if not isinstance(grid, str):
        raise ValueError("grid locator must be a string")

    g = grid.strip().upper()
    if len(g) not in (4, 6):
        raise ValueError(f"grid locator must be 4 or 6 characters, got {len(g)}")

    lon_field = _letter_index(g[0], "R")
    lat_field = _letter_index(g[1], "R")

    if g[2] not in "0123456789" or g[3] not in "0123456789":
        raise ValueError("square digits must be 0-9")
    lon_square = int(g[2])
    lat_square = int(g[3])

    lon = -180.0 + 20.0 * lon_field + 2.0 * lon_square
    lat = -90.0 + 10.0 * lat_field + 1.0 * lat_square

    if len(g) == 4:
        return (lat + 0.5, lon + 1.0)

    lon_sub = _letter_index(g[4], "X")
    lat_sub = _letter_index(g[5], "X")
    lon += (5.0 / 60.0) * (lon_sub + 0.5)
    lat += (2.5 / 60.0) * (lat_sub + 0.5)
    return (lat, lon)


def latlon_to_maidenhead(lat: float, lon: float, precision: int = 6) -> str:
    """Convert latitude/longitude to a 4- or 6-character Maidenhead locator."""
    if precision not in (4, 6):
        raise ValueError("precision must be 4 or 6")

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError) as exc:
        raise ValueError("latitude and longitude must be numbers") from exc

    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        raise ValueError("latitude and longitude must be finite")
    if not -90.0 <= lat_f <= 90.0:
        raise ValueError("latitude must be between -90 and 90")
    if not -180.0 <= lon_f <= 180.0:
        raise ValueError("longitude must be between -180 and 180")

    lat_f = min(89.999999999, lat_f)
    lon_f = min(179.999999999, lon_f)

    lon_shift = lon_f + 180.0
    lat_shift = lat_f + 90.0

    lon_field = min(17, int(lon_shift // 20.0))
    lat_field = min(17, int(lat_shift // 10.0))
    lon_rem = lon_shift - 20.0 * lon_field
    lat_rem = lat_shift - 10.0 * lat_field

    lon_square = min(9, int(lon_rem // 2.0))
    lat_square = min(9, int(lat_rem // 1.0))
    lon_sub = min(23, int((lon_rem - 2.0 * lon_square) * 12.0))
    lat_sub = min(23, int((lat_rem - 1.0 * lat_square) * 24.0))

    locator = f"{chr(65 + lon_field)}{chr(65 + lat_field)}{lon_square}{lat_square}"
    if precision == 6:
        locator += f"{chr(97 + lon_sub)}{chr(97 + lat_sub)}"
    return locator
