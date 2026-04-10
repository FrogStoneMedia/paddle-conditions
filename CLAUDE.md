# Paddle Conditions HACS Integration

> **Part of the Paddle Conditions monorepo.** This is one of four sibling repos (hacs, api, app, website). Shared workspace rules live in `../CLAUDE.md` at the root: changelog + docs update on every change, "Paddle Conditions" two words, no em-dashes in public copy, no `Co-Authored-By` in commits. This repo is the only Python one — npm rules don't apply here. If you opened this repo in isolation, read `../CLAUDE.md` first.

## Stack
Home Assistant custom component, Python 3.11+. Dashboard cards are bundled Lovelace custom cards under `custom_components/paddle_conditions/www/`. Frontend dev sources in `frontend/`. pytest for tests.

## Public repo
This is the only public repo in the project: `FrogStoneMedia/paddle-conditions` on GitHub. Treat it accordingly — no internal URLs, no secrets, no references to proprietary backend endpoints that aren't meant to be public.

## Commands
- `python -m pytest tests/` - run all tests
- `python -m pytest tests/test_sensor.py -v` - run a single test file
- `python3 -m ruff check .` - lint
- `python3 -m ruff format .` - format

## Architecture
- `custom_components/paddle_conditions/` - the HA integration proper (`__init__.py`, `config_flow.py`, `sensor.py`, `coordinator.py`, `api/` wrappers)
- `custom_components/paddle_conditions/www/` - bundled dashboard cards (shipped with the integration, loaded by HA Lovelace)
- `frontend/` - card source before bundling to `www/`
- `ha-integration/` - separate scratch area, check CLAUDE context when touching

## Conventions
- Any user-visible string (entity names, config flow text, card labels): "Paddle Conditions" two words. No em-dashes.
- HA lifecycle discipline: `async_setup_entry`, `async_unload_entry`, clean up listeners.
- Tests use pytest with HA test fixtures. Mock external APIs, do not hit the real backend.

## HACS submission
v1.0.0 has been released. HACS PR #6225 is pending review. Once merged, users can install via HACS directly.

## Changelog
Changes here still go in `../website/data/changelog.json` even though this is a public GitHub repo with its own `CHANGELOG.md`. The website changelog is the canonical cross-repo history. Update both in the same commit. Use `/log-change` to draft.
