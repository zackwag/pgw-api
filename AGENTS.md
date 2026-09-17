# AGENTS.md

## Project overview

Unofficial async Python API client for Philadelphia Gas Works (PGW), built on `aiohttp`. Published to PyPI as `pgw-api`; consumed by the `ha-pgw` Home Assistant integration.

## Setup

```sh
pip install .
pip install pytest pytest-asyncio
```

## Build / Run

N/A — this is a library, not a standalone application. `pyproject.toml` uses setuptools; `python -m build` produces a wheel/sdist if a release build is needed.

## Test

```sh
pytest
```

Config: `pyproject.toml` (`asyncio_mode = "auto"`). Requires Python >= 3.12.

## Repository structure

- `pgw_api/` — the client library
- `tests/` — pytest suite
- `openapi.yaml` — OpenAPI spec documenting the (reverse-engineered) PGW API surface this client wraps

## Commit and PR conventions

- Commit messages and PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `build:`, `perf:`, `style:`, `revert:`), optionally with a scope, e.g. `fix(api): handle null response`.
- This repo squash-merges pull requests only; the PR title becomes the final commit message on `main`.
- A "Conventional Commits" CI check enforces this on both PR titles and direct-push commit messages.
- Branch protection on `main`: no force-pushes, no branch deletion, required status checks must pass.
