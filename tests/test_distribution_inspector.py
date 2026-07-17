import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inspect_distribution import (
    EXPECTED_ENTRY_POINTS,
    GOVERNANCE_DOCUMENTS,
    Archive,
    path_errors,
    residue_errors,
    source_files,
)


def archive(kind: str, names: tuple[str, ...]) -> Archive:
    return Archive(Path("artifact"), kind, names, {name: b"" for name in names})


def test_member_paths_reject_unsafe_and_nonportable_forms() -> None:
    errors = path_errors(
        (
            "../escape",
            "/absolute",
            "folder\\file",
            "C:/drive",
            "folder//file",
            "trailing.",
            "duplicate",
            "duplicate",
            "Package/module.py",
            "package/module.py",
        )
    )

    assert any("traversal" in error for error in errors)
    assert any("absolute" in error for error in errors)
    assert any("backslash" in error for error in errors)
    assert any("drive-qualified" in error for error in errors)
    assert any("non-portable segments" in error for error in errors)
    assert any("trailing character" in error for error in errors)
    assert any("duplicate member path" in error for error in errors)
    assert any("case-insensitive path collision" in error for error in errors)


def test_setuptools_egg_info_is_allowed_only_at_sdist_root() -> None:
    root = "world_consistency_linter-0.3.0"
    valid = archive("sdist", (f"{root}/world_consistency_linter.egg-info/PKG-INFO",))
    misplaced = archive(
        "sdist",
        (f"{root}/nested/world_consistency_linter.egg-info/PKG-INFO",),
    )

    assert residue_errors(valid, root) == []
    assert any("unexpected egg-info" in error for error in residue_errors(misplaced, root))


def test_wheel_rejects_egg_info_reports_and_development_residue() -> None:
    candidate = archive(
        "wheel",
        (
            "world_consistency_linter.egg-info/PKG-INFO",
            ".pytest_cache/state",
            "worldlint_output/worldlint_report.json",
        ),
    )

    errors = residue_errors(candidate, "unused")
    assert any("unexpected egg-info" in error for error in errors)
    assert sum("forbidden development path" in error for error in errors) == 2


def test_sdist_requires_single_top_level_directory() -> None:
    root = "world_consistency_linter-0.3.0"
    candidate = archive("sdist", (f"{root}/README.md", "outside.txt"))

    assert any("outside its single top-level directory" in error for error in residue_errors(candidate, root))


def test_sdist_contract_preserves_examples_and_binary_fixtures() -> None:
    repository = ROOT

    assert source_files(repository, "examples") == {
        "examples/airedale_certificate.txt",
        "examples/harlow_letter.txt",
        "examples/minimal_manifest.yaml",
        "examples/study_plan.txt",
    }
    fixture_files = source_files(repository, "tests/fixtures")
    assert any(path.endswith(".pdf") for path in fixture_files)
    assert any(path.endswith(".docx") for path in fixture_files)
    assert any(path.endswith(".xlsx") for path in fixture_files)


def test_wcl_entry_point_contract_is_exact() -> None:
    assert EXPECTED_ENTRY_POINTS == {
        "wcl": "world_consistency_linter.cli:main",
        "world-consistency-linter": "world_consistency_linter.cli:main",
    }


def test_sdist_contract_requires_all_governance_documents() -> None:
    assert GOVERNANCE_DOCUMENTS == {
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "DESIGN.md",
        "SECURITY.md",
    }
