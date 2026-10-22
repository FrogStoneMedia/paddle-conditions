# Paddle Conditions HACS Integration

> **Part of the Paddle Conditions monorepo.** This is one of four sibling repos (hacs, api, app, website). Shared workspace rules live in `../CLAUDE.md` at the root: changelog + docs update on every change, "Paddle Conditions" two words, no em-dashes in public copy, no `Co-Authored-By` in commits. This repo is the only Python one. The workspace npm rules (exact pins, committed lockfile, `npm ci --ignore-scripts`, 10-day cooldown) apply to `frontend/`. If you opened this repo in isolation, read `../CLAUDE.md` first.

## Stack
Home Assistant custom component, Python 3.14 (HA 2026.9+ minimum, set in `hacs.json`). Config flow schemas use `probatio` (core replaced voluptuous in 2026.9). Dashboard cards are one ES module built from `frontend/src` into `custom_components/paddle_conditions/frontend/dist/paddle-cards.js` (committed, registered by `frontend.py`). pytest for Python, `node --test` for the card libraries.

## Public repo
This is the only public repo in the project: `FrogStoneMedia/paddle-conditions` on GitHub. Treat it accordingly — no internal URLs, no secrets, no references to proprietary backend endpoints that aren't meant to be public.

## Commands
- `pip install -r requirements_test.txt` - pinned test set (HA test harness, mypy, ruff); bump only to releases older than 10 days
- `python -m pytest tests/ --cov=custom_components/paddle_conditions` - run all tests (CI fails under 95%)
- `python -m mypy` - strict typing against the installed HA (config in pyproject.toml)
- `python -m ruff check .` / `python -m ruff format .` - lint / format

## Architecture
- `custom_components/paddle_conditions/` - the HA integration proper (`__init__.py`, `config_flow.py`, `sensor.py`, `coordinator.py`, `api/` wrappers)
- `frontend/src/cards/` - the six cards; `frontend/src/lib/` - shared modules (registry-based sibling lookup, unit conversion, time zone, daylight, contrast-tested palette, native `<dialog>`, accessible mini charts)
- `frontend/` build: `npm ci --ignore-scripts && npm test && npm run build`. Commit the rebuilt `dist/paddle-cards.js` with the source; CI fails if they differ.
- Cards keep `paddle-score-card` / `paddle-spots-card` names and config forever; existing dashboards depend on them.

## Conventions
- Any user-visible string (entity names, config flow text, card labels): "Paddle Conditions" two words. No em-dashes.
- HA lifecycle discipline: `async_setup_entry`, `async_unload_entry`, clean up listeners.
- Tests run against a real `hass` and a real config entry (`config_entry`, `mock_apis`, `setup_integration` in `tests/conftest.py`), with upstream HTTP mocked through `aioclient_mock`. Don't add MagicMock-hass tests; they hid real HA behaviour before.
- Advancing time: `freezer.tick(...)`, `async_fire_time_changed(hass)`, then `await hass.async_block_till_done(wait_background_tasks=True)`. Coordinator refreshes run as entry background tasks, so without `wait_background_tasks` polls land on every other tick.
- Any test that adds a location must use `mock_apis`, or the reload reaches for the real internet.

## Testing cards in a real Home Assistant
A throwaway HA in the scratchpad (config with the integration symlinked in, `unit_system: metric`) plus Playwright is how the cards were verified. Don't start it with `--skip-pip`: core service descriptions then fail and the frontend never finishes loading. The bundle URL is `?v=<manifest version>` with a 31-day cache and HA's service worker caches it too, so after a local rebuild clear both (CDP `Network.clearBrowserCache` + `Storage.clearDataForOrigin` service_workers,cache_storage) or you will be testing the old bundle.

## HACS
In the HACS default store since 2026-05-12 (hacs/default PR #6225). From HA 2026.11, HACS ships in core as "Marketplace"; `hacs.json` and the manifest `version`/`issue_tracker` keys still apply.

## CI
Tests, Lint and typing run on GitHub-hosted runners. This repo is public and `pull_request` runs contributor code, so never move PR jobs to the self-hosted runner. Release (tags only) stays self-hosted.

## Changelog
Changes here still go in `../website/data/changelog.json` even though this is a public GitHub repo with its own `CHANGELOG.md`. The website changelog is the canonical cross-repo history. Update both in the same commit. Use `/log-change` to draft.
