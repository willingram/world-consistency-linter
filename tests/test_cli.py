from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import distribution
from types import SimpleNamespace

import pytest

from world_consistency_linter import __version__, cli
from world_consistency_linter.cli import main
from world_consistency_linter.models import ExtractionResult, Finding


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, check=False, text=True)


@pytest.mark.parametrize("command", ["wcl", "world-consistency-linter"])
@pytest.mark.parametrize("option", ["--help", "--version"])
def test_installed_console_scripts(command: str, option: str) -> None:
    executable = shutil.which(command)
    assert executable is not None

    result = run_command([executable, option])

    assert result.returncode == 0
    if option == "--help":
        assert result.stdout.startswith("usage: wcl ")
    else:
        assert result.stdout.strip() == f"wcl {__version__}"


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_module_invocation(option: str) -> None:
    result = run_command([sys.executable, "-m", "world_consistency_linter", option])

    assert result.returncode == 0
    if option == "--help":
        assert result.stdout.startswith("usage: wcl ")
    else:
        assert result.stdout.strip() == f"wcl {__version__}"


def test_distribution_exposes_only_canonical_console_scripts() -> None:
    console_scripts = {
        entry_point.name: entry_point.value
        for entry_point in distribution("world-consistency-linter").entry_points
        if entry_point.group == "console_scripts"
    }

    assert console_scripts == {
        "wcl": "world_consistency_linter.cli:main",
        "world-consistency-linter": "world_consistency_linter.cli:main",
    }


def test_cli_diagnostic_prefix_uses_wcl(tmp_path, capsys) -> None:
    missing_manifest = tmp_path / "missing.yaml"

    assert main(["--manifest", str(missing_manifest), "--out", str(tmp_path / "out")]) == 3
    assert capsys.readouterr().out.startswith("wcl: manifest error:")


def configure_cli_decision_path(monkeypatch, finding: Finding, errors: list[str] | None = None) -> None:
    extraction = ExtractionResult([], errors or [], [], [])
    monkeypatch.setattr(cli, "load_manifest", lambda _path: SimpleNamespace(files=[]))
    monkeypatch.setattr(cli, "extract_all", lambda _files: extraction)
    monkeypatch.setattr(cli, "extract_mentions", lambda _chunks, _manifest: [])
    monkeypatch.setattr(cli, "run_checks", lambda _manifest, _chunks, _mentions: [finding])
    monkeypatch.setattr(cli, "write_reports", lambda *_args: None)


@pytest.mark.parametrize(
    ("threshold", "loudness", "expected"),
    [
        ("GLANCE", "GLANCE", 2),
        ("GLANCE", "STANDARD", 0),
        ("GLANCE", "DEEP", 0),
        ("STANDARD", "GLANCE", 2),
        ("STANDARD", "STANDARD", 2),
        ("STANDARD", "DEEP", 0),
        ("DEEP", "GLANCE", 2),
        ("DEEP", "STANDARD", 2),
        ("DEEP", "DEEP", 2),
    ],
)
def test_fail_on_threshold_matrix_uses_real_cli_decision_path(
    monkeypatch,
    tmp_path,
    threshold: str,
    loudness: str,
    expected: int,
) -> None:
    finding = Finding("test", "Synthetic finding", loudness, "UNINTENDED", "summary", [])
    configure_cli_decision_path(monkeypatch, finding)

    result = main(
        [
            "--manifest",
            str(tmp_path / "manifest.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--fail-on",
            threshold,
        ]
    )

    assert result == expected


@pytest.mark.parametrize("threshold", ["GLANCE", "STANDARD", "DEEP"])
def test_intended_findings_never_fail_threshold(monkeypatch, tmp_path, threshold: str) -> None:
    finding = Finding("test", "Synthetic finding", "GLANCE", "INTENDED", "summary", [])
    configure_cli_decision_path(monkeypatch, finding)

    result = main(
        [
            "--manifest",
            str(tmp_path / "manifest.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--fail-on",
            threshold,
        ]
    )

    assert result == 0


@pytest.mark.parametrize("threshold", ["GLANCE", "STANDARD", "DEEP"])
def test_hard_input_errors_return_three_independent_of_threshold(monkeypatch, tmp_path, threshold: str) -> None:
    finding = Finding("test", "Synthetic finding", "DEEP", "UNINTENDED", "summary", [])
    configure_cli_decision_path(monkeypatch, finding, errors=["input failed"])

    result = main(
        [
            "--manifest",
            str(tmp_path / "manifest.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--fail-on",
            threshold,
        ]
    )

    assert result == 3
