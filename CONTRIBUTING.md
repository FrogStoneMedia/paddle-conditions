# Contributing to Paddle Conditions

This guide covers development setup, testing, and how to submit changes.

## Table of contents

- [Development setup](#development-setup)
- [Project structure](#project-structure)
- [TDD workflow](#tdd-workflow)
- [Running tests](#running-tests)
- [Linting](#linting)
- [Pull request guidelines](#pull-request-guidelines)
- [Design principles](#design-principles)

---

## Development setup

### Prerequisites

- Python 3.14 or later
- Git

### Clone and install

```bash
git clone https://github.com/FrogStoneMedia/paddle-conditions.git
cd paddle-conditions

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install test dependencies
pip install -r requirements_test.txt
```

`requirements_test.txt` installs:
- `pytest-homeassistant-custom-component`: HA test harness, mock config entries, mock aiohttp sessions
- `pytest-cov`: coverage reporting

No HA installation needed. The test harness provides everything required to run integration tests without a full Home Assistant instance.

### Verify setup

```bash
# Full test suite
pytest tests/ -v

# Linting
ruff check .

# Single test file
pytest tests/test_scoring.py -v
```

---

## Project structure

```
ha-integration/
├── custom_components/
│   └── paddle_conditions/
│       ├── __init__.py          # Entry setup / teardown
│       ├── config_flow.py       # Config + subentry + options flows
│       ├── coordinator.py       # DataUpdateCoordinator (one per location)
│       ├── sensor.py            # Sensor entity definitions
│       ├── scoring.py           # Scoring engine (pure functions)
│       ├── profiles.py          # Profile definitions (curves, weights, vetoes)
│       ├── models.py            # Data models (PaddleScore, PaddleConditions, etc.)
│       ├── cloud_sync.py        # Cloud sync client
│       ├── const.py             # Constants and config keys
│       ├── diagnostics.py       # HA diagnostics with key redaction
│       └── api/
│           ├── base.py          # Base API client (retry, timeout)
│           ├── open_meteo.py    # Weather + AQI clients
│           ├── usgs.py          # USGS water data client
│           └── noaa.py          # NOAA tide/temperature client
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── fixtures/                # Recorded API responses
│   ├── test_scoring.py
│   ├── test_profiles.py
│   ├── test_coordinator.py
│   ├── test_config_flow.py
│   ├── test_sensor.py
│   ├── test_api_open_meteo.py
│   ├── test_api_usgs.py
│   ├── test_api_noaa.py
│   ├── test_cloud_sync.py
│   └── test_diagnostics.py
├── docs/
│   ├── SCORING.md               # Scoring algorithm documentation
│   ├── API-SOURCES.md           # Data source reference
│   └── ARCHITECTURE.md          # System design overview
└── requirements_test.txt
```

---

## TDD workflow

Every change follows test-driven development:

1. **Write a failing test** that describes the desired behavior
2. **Run it** and confirm it fails for the expected reason
3. **Write the minimum code** to make it pass
4. **Refactor** while keeping all tests green
5. **Commit**

### Bug fixes

Write a failing test that reproduces the bug _before_ writing the fix. This keeps it fixed.

### New features

Start with the simplest test case. Build up complexity one test at a time. Each test should describe one behavior.

### What to test

- Scoring functions with boundary values (ideal, marginal, no-go, and values between)
- All 6 profiles (curves, weights, vetoes match expected values)
- API response parsing (valid and malformed responses)
- Config flow steps (initial setup, subentry add/edit, options changes)
- Coordinator behavior (successful fetch, partial failure, full failure)
- Sensor entity creation, unique IDs, state values
- Hard veto conditions
- Missing data and weight renormalization
- Cloud sync push/pull and failure queuing

---

## Running tests

### Full suite

```bash
pytest tests/ -v
```

### With coverage

```bash
pytest tests/ -v --cov=custom_components.paddle_conditions --cov-report=term-missing
```

### Single test file

```bash
pytest tests/test_scoring.py -v
```

### Single test function

```bash
pytest tests/test_scoring.py::test_wind_speed_ideal -v
```

### Tests matching a keyword

```bash
pytest tests/ -v -k "veto"
```

All tests use mocked API responses from `tests/fixtures/`. No live API calls run during testing.

---

## Linting

### Check for errors

```bash
ruff check .
```

### Auto-fix

```bash
ruff check . --fix
```

### Check formatting

```bash
ruff format --check .
```

### Auto-format

```bash
ruff format .
```

All lint and format checks must pass before merging. CI runs these automatically.

---

## Pull request guidelines

### Before submitting

1. All tests pass: `pytest tests/ -v`
2. No lint errors: `ruff check .`
3. Formatting correct: `ruff format --check .`
4. New code has tests (TDD)
5. No secrets, API keys, or credentials in the diff

### PR structure

- **Title**: brief, under 70 characters
- **Description**: what changed and why. Include context a reviewer needs.
- **Test plan**: how the change was tested

### Commit messages

Follow the project prefix convention:

```
[ha-integration] Brief description of the change
```

Keep commits focused. One logical change per commit.

### What makes a good PR

- Small and focused: one feature, one bug fix, or one refactor
- Tests included for every behavioral change
- No unrelated changes (keep formatting, refactors, and features separate)
- Clear description (a reviewer should understand the change from the PR alone)

---

## Design principles

### Kent Beck's simple design rules

1. **Passes the tests**: correctness comes first
2. **Reveals intention**: code should be readable
3. **No duplication**: DRY, but not at the expense of clarity
4. **Fewest elements**: no speculative abstractions, no unused code

### YAGNI

Don't build features that aren't needed yet. If a future requirement is uncertain, don't code for it today.

### Fail visibly

Bad data should cause visible errors, not silent corruption. API clients raise `APIError` on failure. The coordinator propagates `UpdateFailed` for required data sources. Optional sources log warnings and continue.

### Pure functions for scoring

The scoring engine (`scoring.py`) has zero Home Assistant dependencies. It takes raw values in and returns a `PaddleScore` out. Easy to test, reusable across platforms.
