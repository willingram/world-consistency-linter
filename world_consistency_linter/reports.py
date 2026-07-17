from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import ExtractionResult, Finding, Manifest, Mention, TextChunk


def write_reports(
    out_dir: Path,
    manifest: Manifest,
    extraction: ExtractionResult,
    chunks: list[TextChunk],
    mentions: list[Mention],
    findings: list[Finding],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "worldlint_report.md").write_text(
        render_markdown(manifest, extraction, findings),
        encoding="utf-8",
    )
    (out_dir / "worldlint_report.json").write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "hard_errors": extraction.errors,
                "image_only_files": extraction.image_only_files,
                "extractor_disagreements": extraction.extractor_disagreements,
                "findings": [finding.__dict__ for finding in findings],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (out_dir / "entity_index.md").write_text(
        render_entity_index(chunks, mentions),
        encoding="utf-8",
    )


def render_markdown(manifest: Manifest, extraction: ExtractionResult, findings: list[Finding]) -> str:
    lines = ["# World Consistency Linter Report", ""]
    if extraction.errors:
        lines.extend(["## Hard Input Failures", ""])
        for error in extraction.errors:
            lines.append(f"- {error}")
        lines.append("")
    if extraction.image_only_files:
        lines.extend(["## Image-Only Files", ""])
        for file_name in extraction.image_only_files:
            lines.append(f"- {file_name}: no text layer extracted")
        lines.append("")
    if extraction.extractor_disagreements:
        lines.extend(["## Extractor Disagreements", ""])
        for disagreement in extraction.extractor_disagreements:
            lines.append(f"- {disagreement}")
        lines.append("")

    sorted_findings = sorted(
        findings,
        key=lambda item: (item.classification != "UNINTENDED", -item.severity_value(), item.check, item.title),
    )
    if sorted_findings:
        lines.extend(["## Findings", ""])
        for idx, finding in enumerate(sorted_findings, start=1):
            lines.append(f"### {idx}. {finding.title}")
            lines.append("")
            lines.append(f"- Classification: `{finding.classification}`")
            lines.append(f"- Loudness: `{finding.loudness}`")
            lines.append(f"- Check: `{finding.check}`")
            lines.append(f"- Summary: {finding.summary}")
            lines.append("- Evidence:")
            for evidence in _dedupe_evidence(finding.evidence):
                quote = evidence["quote"].replace("\n", " ").strip()
                lines.append(f"  - `{evidence['file']}` [{evidence['channel']}; {evidence['location']}]: {quote}")
            lines.append("")
    else:
        lines.extend(["## Findings", "", "No findings.", ""])

    lines.extend(
        [
            "## Footer",
            "",
            "This is a deterministic screening tool. It uses conservative pattern extraction and will miss "
            "some human-visible claims; review `entity_index.md` for residual manual checks.",
            f"Manifest: `{manifest.path}`",
            "",
        ]
    )
    return "\n".join(lines)


def _dedupe_evidence(evidence: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for item in evidence:
        key = (item["file"], item["channel"], " ".join(item["quote"].split()))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def render_entity_index(chunks: list[TextChunk], mentions: list[Mention]) -> str:
    lines = ["# Entity Index", ""]
    by_kind: dict[str, list[Mention]] = defaultdict(list)
    for mention in mentions:
        by_kind[mention.kind].append(mention)

    for kind in sorted(by_kind):
        lines.append(f"## {kind}")
        lines.append("")
        for mention in sorted(by_kind[kind], key=lambda item: (item.value.lower(), item.source.file, item.source.location)):
            canonical = f" -> {mention.canonical}" if mention.canonical and mention.canonical != mention.value else ""
            attrs = f" {mention.attributes}" if mention.attributes else ""
            lines.append(
                f"- `{mention.value}`{canonical}{attrs}: `{mention.source.file}` "
                f"[{mention.source.channel}; {mention.source.location}]"
            )
        lines.append("")

    lines.extend(["## Extracted Chunks", ""])
    for chunk in chunks:
        preview = chunk.text.replace("\n", " ").strip()[:240]
        lines.append(f"- `{chunk.source.file}` [{chunk.source.channel}; {chunk.source.location}]: {preview}")
    lines.append("")
    return "\n".join(lines)
