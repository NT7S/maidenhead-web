# Maidenhead Grid Tools

Convert latitude/longitude to a Maidenhead grid locator and back, geocode a
street address, or click a world map to drop a pin.

The published site is **pure static HTML/CSS/JS** — no backend, no build step,
no API keys. `static/` is the entire deployable artifact and can be served by
GitHub Pages, S3, nginx, or `python3 -m http.server`.

## Run locally

```bash
make run
```

Then open http://127.0.0.1:8000. (`make run` is just
`python3 -m http.server -d static`; any static file server works.)

## Deploy to GitHub Pages

1. Push this repository to GitHub with the default branch named `main`.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment → Source**, choose **GitHub Actions**.
4. Push to `main` (or run the **Deploy static site to GitHub Pages** workflow
   manually from the Actions tab).

`.github/workflows/pages.yml` uploads `static/` with
`actions/upload-pages-artifact` (`path: static`) and deploys it with
`actions/deploy-pages`. All asset paths in `index.html` are relative, so the
site works at `https://<user>.github.io/<repo>/` without configuration.

## Features

- **Lat/lon → grid** and **grid → lat/lon** with 4- and 6-character locators.
- **Address lookup** via OpenStreetMap Nominatim, called directly from the
  browser (no proxy).
- **Map click** drops a pin and fills in the grid and coordinates.
- Conversions run locally in `static/grid.js` (`window.Maidenhead`); the page
  never calls a backend API.

## Geocoding notes

Address lookup calls
`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=...`
directly from the browser. It is throttled to **one request per second** and
results are cached in `localStorage` for **24 hours**. There are no API keys
and no server-side environment variables.

Public Nominatim is intended for low-traffic use only. Do not point a busy
site at it — use your own Nominatim instance or a commercial geocoder. The
browser cannot set a custom `User-Agent`; requests are identified by the
`Referer` header, which Nominatim accepts for browser use. Address strings are
sent to OpenStreetMap's servers.

## Tests

```bash
make setup    # create .venv, install pytest + Playwright, download Chromium
make test     # full suite
make test-unit  # grid.py and static-site checks, no browser
make test-ui    # browser tests: grid.js parity and UI flows
```

Requires Python 3.12+ (tested on 3.14) and Chromium for the browser tests.
Browser tests mock Nominatim with `page.route` and block map tiles, so they do
not need third-party network access.

`grid.py` is the Python reference implementation; `static/grid.js` is its
browser port. `tests/test_grid.py` pins the reference behaviour and
`tests/test_grid_js.py` asserts the JavaScript matches it value-for-value.

## Layout

```text
maidenhead-web/
├── .github/workflows/pages.yml   GitHub Pages deployment
├── Makefile
├── README.md
├── requirements-dev.txt
├── grid.py                       Python reference implementation (tests only)
├── static/                       the deployable site
│   ├── index.html
│   ├── styles.css
│   ├── grid.js                   window.Maidenhead conversions
│   ├── app.js                    UI, Nominatim client, throttle + cache
│   └── vendor/leaflet/           vendored Leaflet 1.9.4 (no CDN dependency)
└── tests/
    ├── test_grid.py              Python conversion tests
    ├── test_grid_js.py           JS/Python parity tests in Chromium
    ├── test_site.py              static artifact checks
    └── test_ui.py                browser UI tests
```

## Scope and behaviour

- 4-character (field + square) and 6-character (field + square + subsquare)
  locators only; 8-character extended locators are out of scope.
- `gridToLatLon` / `maidenhead_to_latlon` return the **center** of the square.
- Exact latitude 90 and longitude 180 are clamped into the last valid cell
  (`RR99`); −90/−180 map to `AA00`.
- Map tiles still come from OpenStreetMap over the network; the app shell and
  Leaflet are served locally, so the page loads without a CDN.
