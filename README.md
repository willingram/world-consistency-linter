# World Consistency Linter

Offline command-line tool for checking whether a bundle of documents tells a
consistent world story. It reads a manifest describing the payload and optional
canon, extracts document claims, and writes Markdown and JSON reports.

The linter is intended to catch cross-document seams such as inconsistent person
titles, citation dates that cannot work, non-monotonic timestamps in chronological
records, and repeated incidental details across supposedly independent documents.
It is deterministic and does not call an LLM. Recall is intentionally conservative:
the report should be treated as a screening pass plus an entity index for faster
manual review.

## Install

Requires Python 3.10 or newer.

### With uv

```sh
git clone <repo-url>
cd world-consistency-linter
uv sync --extra dev
```

Run the CLI from the managed environment:

```sh
uv run wcl --manifest manifest.yaml --out worldlint_output
```

### With pip

macOS, Linux, or WSL:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Then run:

```sh
wcl --manifest manifest.yaml --out worldlint_output
world-consistency-linter --manifest manifest.yaml --out worldlint_output
python -m world_consistency_linter --manifest manifest.yaml --out worldlint_output
```

## Usage

```sh
wcl --manifest manifest.yaml --out worldlint_output
```

Outputs:

- `worldlint_output/worldlint_report.md`
- `worldlint_output/worldlint_report.json`
- `worldlint_output/entity_index.md`

Default behaviour:

- exits `0` when no unintended finding reaches the failure threshold
- exits `2` when any `UNINTENDED` finding is `STANDARD` or louder
- always exits non-zero for missing files, unreadable files, or empty extraction

Use `--fail-on glance` for a stricter run:

```sh
wcl --manifest manifest.yaml --out worldlint_output --fail-on glance
```

## Manifest

Relative file paths are resolved relative to the manifest file.

```yaml
files:
  - path: HFS_capability_requirement_letter_PB-1140.pdf
    purported_author: "J. Okafor"
    purported_org: "Harlow Fluid Systems"
    purported_date: 2026-05-14
    independent_of: [gauge_RR_summary_spigot_OD_mar2026.pdf]

entities:
  people:
    - name: "Sarah Fenwick"
      aliases: ["S. Fenwick", "Fenwick"]
      title: "Quality Manager"
      org: "Ansford Manufacturing Group"
  orgs:
    - name: "Harlow Fluid Systems"
      aliases: ["HFS", "Harlow"]
      address: "34 Riverway Trade Estate"
  ids:
    - {id: "PB-1140", kind: part}
    - {id: "QF114", kind: form}

doc_graph:
  - from: PB-1140_capability_study_plan_may2026.docx
    cites: HFS_capability_requirement_letter_PB-1140.pdf

unique_titles:
  - "Quality Manager"

intended_findings: []
```

Everything beyond `files[].path` is optional. More canon allows stronger checks.

## Checks

Current check families:

- Person-title and person-organisation conflicts against canon and across files.
- Role-collision checks for singular titles, driven by `unique_titles` and canon
  titles.
- Unknown person-title notes when a people canon is declared but a titled person
  is absent from it.
- Citation-order violations from manifest `doc_graph` edges and simple in-text
  references such as "letter of 14 May 2026".
- Timestamp monotonicity inside files that look chronological.
- Calendar truth for weekday/date pairs.
- Canon address and ID conflicts where a document attributes a different value.
- Metadata-vs-manifest author/date checks when manifest values are declared.
- Incidental-detail repetition across independent documents.
- Long phrasing overlap across different purported authors.

Findings are classified as `INTENDED` when they match an `intended_findings`
entry. Other findings remain `UNINTENDED`.

## Development

With uv:

```sh
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format .
```

With pip:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format .
```

The test fixtures under `tests/fixtures` are synthetic document bundles used to
exercise known consistency-failure modes.

To validate the publishable artifacts without uploading them, start with no
existing `dist` directory and run:

```sh
uv run --frozen python -m build
uv run --frozen twine check --strict dist/*
uv run --frozen python scripts/inspect_distribution.py dist
```

These commands build and inspect one wheel and one source distribution locally.
They do not upload to PyPI or any other package index. CI additionally installs
the wheel into an isolated environment and exercises every supported command
outside the source tree.

## Repository Notes

- Generated reports, build artifacts, virtual environments, and caches are ignored
  by Git.
- Licensed under the MIT License. See `LICENSE`.
