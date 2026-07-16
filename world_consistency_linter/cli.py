from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .checks import run_checks
from .extractors import extract_all
from .manifest import load_manifest
from .models import LOUDNESS_ORDER
from .patterns import extract_mentions
from .reports import write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wcl",
        description="Audit document bundles for cross-document world consistency.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--manifest", required=True, type=Path, help="Path to manifest.yaml")
    parser.add_argument("--out", required=True, type=Path, help="Output report directory")
    parser.add_argument(
        "--fail-on",
        default="STANDARD",
        choices=["GLANCE", "STANDARD", "DEEP", "glance", "standard", "deep"],
        help="Fail when an unintended finding reaches this loudness or higher.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest.resolve())
    except Exception as exc:  # noqa: BLE001 - CLI should report parse errors cleanly
        print(f"wcl: manifest error: {exc}")
        return 3

    extraction = extract_all(manifest.files)
    mentions = extract_mentions(extraction.chunks, manifest)
    findings = run_checks(manifest, extraction.chunks, mentions)
    write_reports(args.out, manifest, extraction, extraction.chunks, mentions, findings)

    if extraction.errors:
        print(f"wcl: hard input failure; see {args.out / 'worldlint_report.md'}")
        return 3

    threshold = LOUDNESS_ORDER[args.fail_on.upper()]
    failing = [
        finding
        for finding in findings
        if finding.classification == "UNINTENDED" and finding.severity_value() >= threshold
    ]
    if failing:
        print(f"wcl: {len(failing)} unintended finding(s); see {args.out / 'worldlint_report.md'}")
        return 2

    print(f"wcl: pass; see {args.out / 'worldlint_report.md'}")
    return 0
