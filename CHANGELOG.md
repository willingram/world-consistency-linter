# Changelog

All notable changes use a Keep a Changelog-style structure. The project follows
semantic versioning for the CLI and Python package.

No versioned Git tags or releases have been published from this repository.
Current work is recorded under `Unreleased` without implying publication to
PyPI or another package index.

## [Unreleased]

### Added

- Offline manifest-driven screening for cross-document consistency across text,
  delimited, PDF, Word, PowerPoint, and modern Excel document channels.
- Canon-aware entity and claim extraction; citation, calendar, chronology,
  role, metadata, incidental-detail, and phrasing checks; intended-finding
  classification; and configurable loudness thresholds.
- Markdown and JSON findings plus a Markdown entity/chunk index.
- Frozen dependency resolution and cross-platform CI on the minimum and latest
  declared Python versions.
- Wheel and source-distribution builds, strict metadata validation,
  adversarial artifact-content inspection, and isolated installed-command
  smoke tests.
- Contribution, design, security, and changelog documentation.
- Exact package metadata links for the project homepage, source repository,
  issue tracker, and changelog.

### Changed

- Standardized supported invocations on `wcl`,
  `world-consistency-linter`, and `python -m world_consistency_linter`, with
  consistent help and version behavior.
- Kept public examples, tests, and the complete synthetic document fixture
  corpus in the source distribution while retaining a lean runtime wheel.
- Documented the tested loudness contract: `GLANCE` is most visible, the
  default `STANDARD` threshold fails `GLANCE` and `STANDARD`, and `DEEP` fails
  all loudness levels.

### Fixed

- Corrected README guidance that had described `--fail-on glance` as stricter;
  `--fail-on deep` is the strictest existing threshold. Exhaustive CLI-path
  regression coverage now fixes the documented contract without changing
  production behavior.
- Aligned documented command names, installed entry points, and the argparse
  program name.

### Security

- Reject release artifacts containing unsafe archive paths, links or special
  members, common credential material, local path markers, or development
  residue during distribution validation.
- Document the local-document parsing threat model, unbounded-resource risks,
  report-disclosure boundary, and private vulnerability-reporting policy.
