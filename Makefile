PYTHON ?= .venv/bin/python
PYTEST ?= $(PYTHON) -m pytest
PORT ?= 8000

# Keep Playwright browsers inside the project so the suite does not depend on
# a globally configured PLAYWRIGHT_BROWSERS_PATH.
export PLAYWRIGHT_BROWSERS_PATH := $(CURDIR)/.playwright-browsers

.PHONY: help setup test test-unit test-ui run

help:
	@echo "make setup      create .venv and install dependencies + Chromium"
	@echo "make test       run all tests"
	@echo "make test-unit  run conversion and static-site tests (no browser)"
	@echo "make test-ui    run browser tests (grid.js parity + UI)"
	@echo "make run        serve static/ on http://127.0.0.1:8000"

setup:
	python3 -m venv --clear .venv
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m playwright install chromium

test:
	$(PYTEST) -q

test-unit:
	$(PYTEST) -q tests/test_grid.py tests/test_site.py

test-ui:
	$(PYTEST) -q tests/test_grid_js.py tests/test_ui.py

run:
	$(PYTHON) -m http.server -d static $(PORT)
