from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import distribution

import pytest

from world_consistency_linter import __version__
from world_consistency_linter.cli import main


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
