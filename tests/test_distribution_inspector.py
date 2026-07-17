import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inspect_distribution import (
    EXPECTED_ENTRY_POINTS,
    EXPECTED_PROJECT_URLS,
    GOVERNANCE_DOCUMENTS,
    Archive,
    path_errors,
    project_url_errors,
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


def test_project_url_contract_accepts_only_the_exact_four_urls() -> None:
    payload = _metadata_with_urls(EXPECTED_PROJECT_URLS)

    assert project_url_errors(payload, "wheel METADATA") == []
    assert project_url_errors(payload, "sdist PKG-INFO") == []


def test_project_url_contract_rejects_missing_wrong_and_extra_urls() -> None:
    missing = dict(EXPECTED_PROJECT_URLS)
    missing.pop("Issues")
    wrong = dict(EXPECTED_PROJECT_URLS)
    wrong["Repository"] = "https://example.invalid/wrong"
    extra = {**EXPECTED_PROJECT_URLS, "Documentation": "https://example.invalid/docs"}

    for urls in (missing, wrong, extra):
        errors = project_url_errors(_metadata_with_urls(urls), "METADATA")
        assert any("Project-URLs are" in error for error in errors)


def test_project_url_contract_rejects_malformed_and_duplicate_labels() -> None:
    exact_lines = [f"Project-URL: {label}, {url}" for label, url in EXPECTED_PROJECT_URLS.items()]
    payload = (
        "\n".join(
            [
                "Metadata-Version: 2.4",
                *exact_lines,
                exact_lines[0],
                "Project-URL: malformed",
                "",
                "",
            ]
        )
    ).encode()

    errors = project_url_errors(payload, "METADATA")

    assert any("duplicate Project-URL label" in error for error in errors)
    assert any("malformed Project-URL" in error for error in errors)


def _metadata_with_urls(urls: dict[str, str]) -> bytes:
    lines = [
        "Metadata-Version: 2.4",
        *(f"Project-URL: {label}, {url}" for label, url in urls.items()),
        "",
        "",
    ]
    return "\n".join(lines).encode()
