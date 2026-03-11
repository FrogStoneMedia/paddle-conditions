# Contributing to Paddle Conditions

Thanks for your interest in contributing to Paddle Conditions. This guide covers development setup, testing workflow, and how to submit changes.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [TDD Workflow](#tdd-workflow)
- [Running Tests](#running-tests)
- [Linting](#linting)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Design Principles](#design-principles)

---

## Development Setup

### Prerequisites

- Python 3.12 or later
- Git

### Clone and Install

```bash
git clone https://github.com/FrogStoneMedia/paddle-conditions.git
cd paddle-conditions

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install test dependencies
pip install -r requirements_test.txt
```

The `requirements_test.txt` file installs:
- `pytest-homeassistant-custom-component` — provides the HA test harness, mock config entries, and mock aiohttp sessions
- `pytest-cov` — coverage reporting

No additional HA installation is needed. The test harness provides everything required to run the integration's tests without a full Home Assistant instance.

### Verify Setup

```bash
# Run the full test suite
pytest tests/ -v

# Run linting
ruff check .

# Run a single test file
pytest tests/test_scoring.py -v
```

---

## Project Structure

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

## TDD Workflow

This project follows strict test-driven development. Every change must follow this cycle:

1. **Write a failing test** that describes the desired behavior
2. **Run the test** and confirm it fails for the expected reason
3. **Write the minimum code** to make the test pass
4. **Refactor** while keeping all tests green
5. **Commit**

### Bug fixes

When fixing a bug, always write a failing test that reproduces the bug _before_ writing the fix. This ensures the bug stays fixed.

### New features

Start with the simplest possible test case. Build up complexity incrementally. Each test should describe one specific behavior.

### What to test

- All scoring functions with boundary values (ideal max, marginal, no-go, and values between)
- All 6 profiles (verify curves, weights, and vetoes match expected values)
- API response parsing (both valid and malformed responses)
- Config flow steps (initial setup, subentry add/edit, options changes)
- Coordinator behavior (successful fetch, partial failure, full failure)
- Sensor entity creation, unique IDs, and state values
- Hard veto conditions
- Missing data / weight renormalization
- Cloud sync push/pull and failure queuing

---

## Running Tests

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

### All tests matching a keyword

```bash
pytest tests/ -v -k "veto"
```

All tests use mocked API responses from `tests/fixtures/`. No live API calls are made during testing.

---

## Linting

### Check for lint errors

```bash
ruff check .
```

### Auto-fix lint errors

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

### Type checking (if configured)

```bash
mypy custom_components/paddle_conditions --strict
```

All lint and format checks must pass before a PR can be merged. CI runs these automatically.

---

## Pull Request Guidelines

### Before submitting

1. All tests pass: `pytest tests/ -v`
2. No lint errors: `ruff check .`
3. Formatting is correct: `ruff format --check .`
4. New code has corresponding tests (TDD)
5. No secrets, API keys, or credentials in the diff

### PR structure

- **Title:** Brief, descriptive summary (under 70 characters)
- **Description:** Explain _what_ changed and _why_. Include context that a reviewer needs.
- **Test plan:** Describe how the change was tested

### Commit messages

Follow the project's commit prefix convention:

```
[ha-integration] Brief description of the change
```

Keep commits focused. One logical change per commit.

### What makes a good PR

- **Small and focused** — one feature, one bug fix, or one refactor per PR
- **Tests included** — every behavioral change has a test
- **No unrelated changes** — keep formatting fixes, refactors, and features in separate PRs
- **Clear description** — a reviewer should understand the change from the PR description alone

---

## Design Principles

These principles guide all development decisions:

### Kent Beck's Simple Design Rules

1. **Passes the tests** — correctness comes first
2. **Reveals intention** — code should be readable and self-documenting
3. **No duplication** — DRY, but not at the expense of clarity
4. **Fewest elements** — no speculative abstractions, no unused code

### YAGNI

Do not build features that are not yet needed. If a future requirement is uncertain, do not code for it today.

### Fail Visibly

Bad data should cause visible errors, not silent corruption. API clients raise `APIError` on failure. The coordinator propagates `UpdateFailed` for required data sources. Optional data sources degrade gracefully with logged warnings.

### Pure Functions for Scoring

The scoring engine (`scoring.py`) has zero Home Assistant dependencies. It takes raw values in, returns a `PaddleScore` out. This makes it trivially testable and reusable across platforms.
