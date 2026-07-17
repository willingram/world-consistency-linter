from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from world_consistency_linter.cli import main

ROOT = Path(__file__).resolve().parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_worldlint(manifest_path: Path, out_dir: Path, fail_on: str = "STANDARD") -> int:
    return main(["--manifest", str(manifest_path), "--out", str(out_dir), "--fail-on", fail_on])


def test_clean_minimal_bundle_passes(tmp_path: Path) -> None:
    write(
        tmp_path / "letter.txt",
        "Harlow Fluid Systems\n34 Riverway Trade Estate\n14 May 2026\nPB-1140 QF114\n",
    )
    write(
        tmp_path / "plan.txt",
        "15 May 2026\nThe study plan follows the letter of 14 May 2026.\nSarah Fenwick, Quality Manager\n",
    )
    manifest = {
        "files": [
            {
                "path": "letter.txt",
                "purported_org": "Harlow Fluid Systems",
                "purported_date": "2026-05-14",
            },
            {
                "path": "plan.txt",
                "purported_org": "Ansford Manufacturing Group",
                "purported_date": "2026-05-15",
            },
        ],
        "entities": {
            "people": [{"name": "Sarah Fenwick", "title": "Quality Manager"}],
            "orgs": [{"name": "Harlow Fluid Systems", "address": "34 Riverway Trade Estate"}],
            "ids": [{"id": "PB-1140", "kind": "part"}, {"id": "QF114", "kind": "form"}],
        },
        "doc_graph": [{"from": "plan.txt", "cites": "letter.txt"}],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out") == 0
    assert (tmp_path / "out" / "entity_index.md").exists()


def test_glance_finding_fails_at_default_standard_threshold(tmp_path: Path) -> None:
    write(tmp_path / "weekday.txt", "Monday 2026-05-19\n")
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({"files": [{"path": "weekday.txt"}]}), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out") == 2
    report = (tmp_path / "out" / "worldlint_report.md").read_text(encoding="utf-8")
    assert "Weekday does not match date" in report


def test_empty_file_is_hard_failure(tmp_path: Path) -> None:
    write(tmp_path / "empty.txt", "")
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({"files": [{"path": "empty.txt"}]}), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out") == 3
    assert "empty extraction" in (tmp_path / "out" / "worldlint_report.md").read_text(encoding="utf-8")


def test_missing_file_is_hard_failure(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({"files": [{"path": "missing.txt"}]}), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out") == 3
    assert "missing file" in (tmp_path / "out" / "worldlint_report.md").read_text(encoding="utf-8")


def test_same_org_documents_are_not_independent_by_default(tmp_path: Path) -> None:
    write(tmp_path / "a.txt", "Ansford note\nUnit 7\n")
    write(tmp_path / "b.txt", "Ansford checklist\nUnit 7\n")
    manifest = {
        "files": [
            {"path": "a.txt", "purported_org": "Ansford Manufacturing Group"},
            {"path": "b.txt", "purported_org": "Ansford Manufacturing Group"},
        ]
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out") == 0


def test_regressed_bundle_catches_four_known_classes(tmp_path: Path) -> None:
    write(tmp_path / "letter.txt", "Harlow Fluid Systems\nUnit 7\n14 May 2026\n")
    write(
        tmp_path / "plan.txt",
        "12 May 2026\nThis plan follows the letter of 14 May 2026.\nSarah Fenwick, Quality Engineer\n",
    )
    write(tmp_path / "cert.txt", "Airedale Metrology\nUnit 7\n20 February 2026\n")
    write(
        tmp_path / "cmm_export.csv",
        "Date,Time,value\n2026-05-18,08:00,12.001\n2026-05-18,08:05,12.002\n2026-05-18,08:03,12.003\n",
    )
    manifest = {
        "files": [
            {
                "path": "letter.txt",
                "purported_org": "Harlow Fluid Systems",
                "purported_date": "2026-05-14",
                "independent_of": ["cert.txt"],
            },
            {
                "path": "plan.txt",
                "purported_org": "Ansford Manufacturing Group",
                "purported_date": "2026-05-12",
            },
            {
                "path": "cert.txt",
                "purported_org": "Airedale Metrology",
                "purported_date": "2026-02-20",
            },
            {"path": "cmm_export.csv", "purported_org": "Ansford Manufacturing Group", "chronological": True},
        ],
        "entities": {
            "people": [{"name": "Sarah Fenwick", "title": "Quality Manager"}],
            "orgs": [{"name": "Harlow Fluid Systems", "address": "34 Riverway Trade Estate"}],
        },
        "doc_graph": [{"from": "plan.txt", "cites": "letter.txt"}],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    assert run_worldlint(manifest_path, tmp_path / "out", fail_on="DEEP") == 2
    report = (tmp_path / "out" / "worldlint_report.md").read_text(encoding="utf-8")
    assert "Person title conflicts with manifest canon" in report
    assert "Document predates a declared citation" in report
    assert "Timestamp sequence is not monotonic" in report
    assert "Repeated incidental address" in report
    data = json.loads((tmp_path / "out" / "worldlint_report.json").read_text(encoding="utf-8"))
    loudness_by_check = {finding["check"]: finding["loudness"] for finding in data["findings"]}
    assert loudness_by_check["person_attribute_conflict"] == "STANDARD"
    assert loudness_by_check["citation_order"] == "STANDARD"
    assert loudness_by_check["timestamp_monotonicity"] == "DEEP"
    assert loudness_by_check["incidental_repetition"] == "STANDARD"


def test_shape_c_fixture_reports_role_collision_and_timestamp(tmp_path: Path) -> None:
    manifest_path = ROOT / "fixtures" / "shape_c_real" / "manifest.yaml"
    if not manifest_path.exists():
        pytest.skip("Shape-C fixture not present")

    assert run_worldlint(manifest_path, tmp_path / "out") == 0
    report = (tmp_path / "out" / "worldlint_report.md").read_text(encoding="utf-8")
    assert "Multiple people hold a singular role" in report
    assert "Sarah Bright" in report
    assert "Graham Fenwick" in report
    assert "Timestamp sequence is not monotonic" in report
    assert "Person-title mention is absent from canon" in report
    assert "Long phrasing overlap" not in report
    assert "Address attributed to canon organisation differs" not in report
