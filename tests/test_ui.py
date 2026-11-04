"""Browser tests for the static app: local conversions, address lookup, map click."""

from __future__ import annotations

import json
import time
import urllib.parse

import pytest

NOMINATIM_PATTERN = "https://nominatim.openstreetmap.org/**"
PORTLAND = [
    {
        "lat": "45.5152",
        "lon": "-122.6784",
        "display_name": "Portland, OR, USA",
    }
]


class NominatimMock:
    """Fake Nominatim response served through Playwright request routing."""

    def __init__(self, page):
        self.page = page
        self.requests = []
        self.responses = {}
        self.default = []
        page.route(NOMINATIM_PATTERN, self._handle)

    def _handle(self, route):
        url = route.request.url
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        query = (params.get("q") or [""])[0]
        self.requests.append({"url": url, "q": query, "t": time.monotonic()})
        payload = self.responses.get(query.strip().lower(), self.default)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        )

    @property
    def count(self):
        return len(self.requests)


@pytest.fixture()
def nominatim(app_page):
    mock = NominatimMock(app_page)
    mock.default = PORTLAND
    return mock


def wait_until(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def submit_address(page, text):
    page.fill("#address", text)
    page.click("#address-form button")


def test_latlon_form_converts_locally(app_page):
    app_page.fill("#lat", "45.5")
    app_page.fill("#lon", "-123")
    app_page.click("#latlon-form button")
    app_page.wait_for_function(
        "document.querySelector('#result-grid').textContent !== '—'"
    )
    grid = app_page.text_content("#result-grid")
    assert grid.startswith("CN85")
    assert len(grid) == 6
    assert app_page.text_content("#result-lat") == "45.500000"
    assert app_page.text_content("#result-lon") == "-123.000000"
    assert app_page.input_value("#grid") == grid


def test_grid_form_converts_locally(app_page):
    app_page.fill("#grid", "CN85pl")
    app_page.click("#grid-form button")
    app_page.wait_for_function(
        "document.querySelector('#result-grid').textContent === 'CN85pl'"
    )
    assert app_page.text_content("#result-lat") == "45.479167"
    assert app_page.text_content("#result-lon") == "-122.708333"
    assert float(app_page.input_value("#lat")) == pytest.approx(45.479166, abs=1e-6)


def test_invalid_grid_shows_error(app_page):
    app_page.fill("#grid", "CN8")
    app_page.click("#grid-form button")
    app_page.wait_for_function(
        "document.querySelector('#status').textContent.length > 0"
    )
    assert "4 or 6" in app_page.text_content("#status")


def test_address_lookup_fills_result_and_map(nominatim):
    page = nominatim.page
    submit_address(page, "Portland, OR")
    page.wait_for_function(
        "document.querySelector('#result-grid').textContent !== '—'"
    )
    assert page.text_content("#result-grid").startswith("CN85")
    assert page.text_content("#result-address") == "Portland, OR, USA"
    assert page.text_content("#result-lat") == "45.515200"
    assert page.text_content("#result-lon") == "-122.678400"
    assert page.evaluate("document.querySelectorAll('.leaflet-marker-icon').length") >= 1


def test_address_lookup_uses_nominatim_directly(nominatim):
    page = nominatim.page
    seen = []
    page.on("request", lambda request: seen.append(request.url))
    submit_address(page, "Portland, OR")
    page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Portland, OR, USA'"
    )
    assert nominatim.count == 1
    request = nominatim.requests[0]
    assert request["url"].startswith("https://nominatim.openstreetmap.org/search?")
    assert "format=jsonv2" in request["url"]
    assert request["q"] == "Portland, OR"
    assert not any("/api/" in url for url in seen), "app must not call a backend API"


def test_latlon_conversion_clears_stale_address(nominatim):
    page = nominatim.page
    submit_address(page, "Portland, OR")
    page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Portland, OR, USA'"
    )
    page.fill("#lat", "0")
    page.fill("#lon", "0")
    page.click("#latlon-form button")
    page.wait_for_function(
        "document.querySelector('#result-grid').textContent === 'JJ00aa'"
    )
    assert page.text_content("#result-address") == "—"


def test_clear_cache_button_removes_only_app_cache(app_page):
    app_page.evaluate(
        """
        () => {
          localStorage.setItem('maidenhead.geocode.v1:test', '{"ts": 1, "value": {}}');
          localStorage.setItem('unrelated-key', 'keep me');
        }
        """
    )
    app_page.click("#clear-cache")
    assert app_page.evaluate("localStorage.getItem('maidenhead.geocode.v1:test')") is None
    assert app_page.evaluate("localStorage.getItem('unrelated-key')") == "keep me"
    assert "cleared" in app_page.text_content("#status").lower()


def test_bad_address_shows_error(app_page):
    app_page.route(
        NOMINATIM_PATTERN,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="[]"
        ),
    )
    submit_address(app_page, "nowhere")
    app_page.wait_for_function(
        "document.querySelector('#status').textContent.includes('not found')"
    )
    assert app_page.text_content("#result-grid") == "—"


def test_map_click_drops_pin_and_fills_fields(app_page):
    app_page.locator("#map").click(position={"x": 500, "y": 200})
    app_page.wait_for_function(
        "document.querySelector('#result-grid').textContent !== '—'"
    )
    assert app_page.text_content("#result-grid") != "—"
    assert app_page.text_content("#result-lat") != "—"
    assert app_page.text_content("#result-lon") != "—"
    assert app_page.evaluate("document.querySelectorAll('.leaflet-marker-icon').length") >= 1


def test_address_lookup_is_cached_for_24_hours(app_page):
    app_page.route(
        NOMINATIM_PATTERN,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [{"lat": "1.5", "lon": "2.5", "display_name": "Cacheville"}]
            ),
        ),
    )
    request_urls = []
    app_page.on(
        "request",
        lambda request: request_urls.append(request.url)
        if "nominatim.openstreetmap.org" in request.url
        else None,
    )

    submit_address(app_page, "Cacheville")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Cacheville'"
    )
    submit_address(app_page, "cacheville")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Cacheville'"
    )

    assert wait_until(lambda: len(request_urls) >= 1)
    time.sleep(0.5)
    assert len(request_urls) == 1

    raw = app_page.evaluate(
        "window.localStorage.getItem('maidenhead.geocode.v1:cacheville')"
    )
    assert raw is not None
    entry = json.loads(raw)
    assert entry["value"]["display_name"] == "Cacheville"
    assert isinstance(entry["ts"], int)


def test_geocode_requests_are_throttled_to_one_per_second(app_page):
    responses = {
        "throttle one": [{"lat": "10", "lon": "20", "display_name": "First Place"}],
        "throttle two": [{"lat": "30", "lon": "40", "display_name": "Second Place"}],
    }

    def handle(route):
        url = route.request.url
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        query = (params.get("q") or [""])[0].strip().lower()
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(responses.get(query, [])),
        )

    app_page.route(NOMINATIM_PATTERN, handle)

    stamps = []
    app_page.on(
        "request",
        lambda request: stamps.append(time.monotonic())
        if "nominatim.openstreetmap.org" in request.url
        else None,
    )

    submit_address(app_page, "Throttle One")
    submit_address(app_page, "Throttle Two")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Second Place'",
        timeout=15000,
    )

    assert wait_until(lambda: len(stamps) >= 2, timeout=5)
    assert max(stamps) - min(stamps) >= 0.9
