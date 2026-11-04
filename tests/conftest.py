"""Shared fixtures: serve static/ with a tiny stdlib server and open Chromium."""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"
NOMINATIM_PATTERN = "https://nominatim.openstreetmap.org/**"
TILE_PATTERN = "https://*.tile.openstreetmap.org/**"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(QuietHandler, directory=str(STATIC))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture()
def app_page(page, base_url):
    """A page with the app loaded, offline-safe tiles, and no real network."""

    page.route(TILE_PATTERN, lambda route: route.abort())
    page.goto(base_url)
    page.wait_for_function("window.__maidenheadReady === true")
    return page
