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


def test_address_lookup_shows_immediate_progress(app_page):
    held = {}
    app_page.route(NOMINATIM_PATTERN, lambda route: held.setdefault("route", route))
    submit_address(app_page, "Progress Place")
    assert wait_until(lambda: "route" in held, timeout=5)

    assert app_page.text_content("#address-status") == "Looking up address…"
    assert app_page.text_content("#address-form button") == "Looking…"
    assert app_page.locator("#address-form button").is_disabled()

    held["route"].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            [{"lat": "45.5152", "lon": "-122.6784", "display_name": "Progress Place"}]
        ),
    )
    app_page.wait_for_function("window.__lastGeocodeSettled >= 1")
    assert app_page.text_content("#address-status") == ""
    assert app_page.text_content("#address-form button") == "Find"


def test_late_address_does_not_overwrite_local_conversion(app_page):
    held = {}

    def hold(route):
        held["route"] = route

    app_page.route(NOMINATIM_PATTERN, hold)
    submit_address(app_page, "Slow Place")
    assert wait_until(lambda: "route" in held, timeout=5)

    app_page.fill("#lat", "0")
    app_page.fill("#lon", "0")
    app_page.click("#latlon-form button")
    app_page.wait_for_function(
        "document.querySelector('#result-grid').textContent === 'JJ00aa'"
    )

    held["route"].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            [{"lat": "10", "lon": "20", "display_name": "Old address overrode local"}]
        ),
    )
    app_page.wait_for_function("window.__lastGeocodeSettled >= 1")

    assert app_page.text_content("#result-grid") == "JJ00aa"
    assert app_page.text_content("#result-address") == "—"


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
    assert wait_until(lambda: len(request_urls) == 1)
    assert len(request_urls) == 1

    # Let the throttle window pass. A second identical query must hit the cache,
    # not the network.
    time.sleep(1.1)
    submit_address(app_page, "cacheville")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Cacheville'"
    )
    time.sleep(0.3)
    assert len(request_urls) == 1

    # Age the cached entry past its TTL and verify the next query refetches.
    app_page.evaluate(
        """
        () => {
          const key = 'maidenhead.geocode.v1:cacheville';
          const entry = JSON.parse(localStorage.getItem(key));
          entry.ts = Date.now() - 25 * 60 * 60 * 1000;
          localStorage.setItem(key, JSON.stringify(entry));
        }
        """
    )
    submit_address(app_page, "Cacheville")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Cacheville'"
    )
    assert wait_until(lambda: len(request_urls) == 2)
    assert len(request_urls) == 2


def test_geocode_requests_are_throttled_to_one_per_second(app_page):
    responses = {
        "throttle one": [{"lat": "10", "lon": "20", "display_name": "First Place"}],
        "throttle two": [{"lat": "30", "lon": "40", "display_name": "Second Place"}],
        "throttle three": [{"lat": "50", "lon": "60", "display_name": "Third Place"}],
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
    submit_address(app_page, "Throttle Three")
    app_page.wait_for_function(
        "document.querySelector('#result-address').textContent === 'Third Place'",
        timeout=15000,
    )

    assert wait_until(lambda: len(stamps) >= 3, timeout=5)
    gaps = [b - a for a, b in zip(sorted(stamps), sorted(stamps)[1:])]
    assert all(gap >= 0.9 for gap in gaps), gaps
