# Contributing

Contributions are welcome. Use Python 3.10 or newer and the frozen uv
environment:

```sh
uv sync --extra dev --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Tests must be deterministic and offline by default. Prefer the smallest
fictional text, CSV, YAML, or generated office-document fixture that exercises
the behavior. The committed binary fixtures are purpose-built synthetic
documents for parser-channel coverage; keep additions small, fictional, and
limited to formats that cannot be represented faithfully as text. Never commit
private documents or data, personal information, credentials, local absolute
paths, generated reports, build artifacts, virtual environments, or caches.

Before proposing a distributable change, start with an empty `dist/` directory
and run the non-publishing artifact checks:

```sh
uv run --frozen python -m build
uv run --frozen twine check --strict dist/*
uv run --frozen python scripts/inspect_distribution.py dist
```

The supported entry points; manifest fields and their semantics; extraction
channels and format handling; checks, finding classifications, loudness ranks,
and failure thresholds; report filenames and fields; and exit behavior are
public-contract areas. Changes to those areas need focused regression tests and
corresponding updates to `README.md`, `DESIGN.md`, and `CHANGELOG.md`.
