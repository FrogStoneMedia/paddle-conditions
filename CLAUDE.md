# Paddle Conditions HACS Integration

> **Part of the Paddle Conditions monorepo.** This is one of four sibling repos (hacs, api, app, website). Shared workspace rules live in `../CLAUDE.md` at the root: changelog + docs update on every change, "Paddle Conditions" two words, no em-dashes in public copy, no `Co-Authored-By` in commits. This repo is the only Python one — npm rules don't apply here. If you opened this repo in isolation, read `../CLAUDE.md` first.

## Stack
Home Assistant custom component, Python 3.14 (HA 2026.9+ minimum, set in `hacs.json`). Config flow schemas use `probatio` (core replaced voluptuous in 2026.9). Dashboard cards are bundled Lovelace custom cards under `custom_components/paddle_conditions/www/` (registered by `frontend.py`). `frontend/` holds the unfinished Chart.js card set that builds to `custom_components/paddle_conditions/frontend/dist/`; it is not registered yet (see `../_todo/20261021-hacs-platinum-refresh.md`, Phase 4). pytest for tests.

## Public repo
This is the only public repo in the project: `FrogStoneMedia/paddle-conditions` on GitHub. Treat it accordingly — no internal URLs, no secrets, no references to proprietary backend endpoints that aren't meant to be public.

## Commands
- `pip install -r requirements_test.txt` - pinned test set (HA test harness, mypy, ruff); bump only to releases older than 10 days
- `python -m pytest tests/ --cov=custom_components/paddle_conditions` - run all tests (CI fails under 95%)
- `python -m mypy` - strict typing against the installed HA (config in pyproject.toml)
- `python -m ruff check .` / `python -m ruff format .` - lint / format

## Architecture
- `custom_components/paddle_conditions/` - the HA integration proper (`__init__.py`, `config_flow.py`, `sensor.py`, `coordinator.py`, `api/` wrappers)
- `custom_components/paddle_conditions/www/` - the two cards users get today (hand-written, registered by `frontend.py`)
- `frontend/` - Chart.js card set source; `npm run build` writes `custom_components/paddle_conditions/frontend/dist/paddle-cards.js`, which nothing registers yet
- `ha-integration/` - separate scratch area, check CLAUDE context when touching

## Conventions
- Any user-visible string (entity names, config flow text, card labels): "Paddle Conditions" two words. No em-dashes.
- HA lifecycle discipline: `async_setup_entry`, `async_unload_entry`, clean up listeners.
- Tests run against a real `hass` and a real config entry (`config_entry`, `mock_apis`, `setup_integration` in `tests/conftest.py`), with upstream HTTP mocked through `aioclient_mock`. Don't add MagicMock-hass tests; they hid real HA behaviour before.
- Advancing time: `freezer.tick(...)`, `async_fire_time_changed(hass)`, then `await hass.async_block_till_done(wait_background_tasks=True)`. Coordinator refreshes run as entry background tasks, so without `wait_background_tasks` polls land on every other tick.
- Any test that adds a location must use `mock_apis`, or the reload reaches for the real internet.

## HACS
In the HACS default store since 2026-05-12 (hacs/default PR #6225). From HA 2026.11, HACS ships in core as "Marketplace"; `hacs.json` and the manifest `version`/`issue_tracker` keys still apply.

## CI
Tests, Lint and typing run on GitHub-hosted runners. This repo is public and `pull_request` runs contributor code, so never move PR jobs to the self-hosted runner. Release (tags only) stays self-hosted.

## Changelog
Changes here still go in `../website/data/changelog.json` even though this is a public GitHub repo with its own `CHANGELOG.md`. The website changelog is the canonical cross-repo history. Update both in the same commit. Use `/log-change` to draft.
