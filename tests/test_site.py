"""The published artifact is plain static files served by any web server."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"

ASSET_RE = re.compile(r'(?:src|href)="([^"]+)"')


def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read()


def test_index_served_with_title(base_url):
    status, body = fetch(f"{base_url}/")
    text = body.decode()
    assert status == 200
    assert "<title>Maidenhead Grid Tools</title>" in text
    assert "static" not in text  # no absolute deploy paths (works under /repo-name/)


def test_every_local_asset_exists(base_url):
    _, body = fetch(f"{base_url}/")
    html = body.decode()
    assets = [a for a in ASSET_RE.findall(html) if not a.startswith(("http://", "https://", "data:"))]
    assert any(a.startswith("grid.js") for a in assets)
    assert any(a.startswith("app.js") for a in assets)
    for asset in assets:
        path = asset.split("?", 1)[0]
        status, content = fetch(f"{base_url}/{path.lstrip('/')}")
        assert status == 200, asset
        assert content, asset


def test_grid_js_loads_before_app_js(base_url):
    _, body = fetch(f"{base_url}/")
    html = body.decode()
    assert html.index("grid.js") < html.index("app.js")


def test_no_api_endpoints(base_url):
    for path in ("/api/health", "/api/convert?lat=45.5&lon=-123", "/api/geocode?q=Portland"):
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"{base_url}{path}", timeout=5)
        assert excinfo.value.code == 404


def test_frontend_converts_locally_and_calls_nominatim_directly():
    app_js = (STATIC / "app.js").read_text()
    grid_js = (STATIC / "grid.js").read_text()
    assert "/api/" not in app_js
    assert "https://nominatim.openstreetmap.org/search" in app_js
    assert "localStorage" in app_js
    assert "window.Maidenhead" in app_js or "Maidenhead.latLonToGrid" in app_js
    assert "global.Maidenhead" in grid_js
    assert "latLonToGrid" in grid_js and "gridToLatLon" in grid_js


def test_static_dir_has_no_python():
    assert not list(STATIC.rglob("*.py"))
    assert not (STATIC / "app.py").exists()


def test_index_uses_vendored_leaflet():
    html = (STATIC / "index.html").read_text()
    assert "vendor/leaflet/leaflet.js" in html
    assert "unpkg.com" not in html


def test_vendored_leaflet_present():
    for name in (
        "vendor/leaflet/leaflet.js",
        "vendor/leaflet/leaflet.css",
        "vendor/leaflet/images/marker-icon.png",
        "vendor/leaflet/images/marker-shadow.png",
    ):
        assert (STATIC / name).is_file(), name
    assert Path(STATIC / "vendor/leaflet/leaflet.js").stat().st_size > 100_000
