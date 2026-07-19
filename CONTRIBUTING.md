# Contributing to ConfigForge

Thanks for your interest in improving ConfigForge! This document explains how
to get set up and what we expect from contributions.

## Getting Started

1. Fork and clone the repository.
2. Create a virtual environment and install dev dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -e ".[dev,secrets]"
   ```
3. Run the tests:
   ```bash
   pytest
   ```

## Development Workflow

- Create a feature branch off `main`: `git checkout -b feat/my-thing`.
- Keep changes focused; add or update tests for any behavior change.
- Run `pytest` and ensure it is green before opening a PR.
- Format with `black .` and lint with `ruff check .` if available.

## Pull Requests

- Describe **what** changed and **why**.
- Link any related issues.
- Ensure CI passes.
- By contributing, you agree your contributions are licensed under the MIT
  License.

## Code of Conduct

This project adheres to the [Contributor Covenant](CODE_OF_CONDUCT.md). Be
respectful and constructive.

## Releasing

Maintainers bump the version in `pyproject.toml` and add a `CHANGELOG.md`
entry, then tag `vX.Y.Z`. CI publishes to PyPI automatically.
