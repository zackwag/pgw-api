# Contributing to pgw-api

Thanks for your interest in improving this unofficial Python API client for Philadelphia Gas Works (PGW).

## Getting started

```sh
git clone https://github.com/zackwag/pgw-api.git
cd pgw-api
pip install .
pip install pytest pytest-asyncio
```

## Development

The client lives in `pgw_api/`. Tests live in `tests/` and use `pytest`:

```sh
pytest
```

The API surface is documented in `openapi.yaml`.

## Commit messages and pull requests

This repo uses [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, etc.). Pull requests are squash-merged, and the **PR title** becomes the commit on `main` — so PR titles must follow this format. This is enforced automatically by the "Conventional Commits" check.

Direct pushes to `main` are allowed but must also use a Conventional Commits-formatted commit message (validated by the same check).

## Opening a pull request

1. Fork the repo and create a branch off `main`.
2. Make your changes.
3. Open a pull request with a Conventional Commits-formatted title.
4. Wait for CI to pass — required checks must be green before merge.

## Reporting issues

Use [GitHub Issues](../../issues) for bugs and feature requests.
