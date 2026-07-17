from __future__ import annotations

import itertools
import re
from collections import defaultdict

from .dates import extract_dates, parse_manifest_date
from .models import FileSpec, Finding, Manifest, Mention, TextChunk


def run_checks(manifest: Manifest, chunks: list[TextChunk], mentions: list[Mention]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_person_attributes(manifest, mentions))
    findings.extend(check_role_collisions(manifest, mentions))
    findings.extend(check_unknown_people(manifest, mentions))
    findings.extend(check_citation_order(manifest, chunks))
    findings.extend(check_timestamp_monotonicity(manifest, mentions))
    findings.extend(check_calendar_truth(mentions))
    findings.extend(check_ambiguity_notes(mentions))
    findings.extend(check_canon_conflicts(manifest, mentions))
    findings.extend(check_metadata_claims(manifest, chunks))
    findings.extend(check_incidental_repetition(manifest, mentions))
    findings.extend(check_phrasing_overlap(manifest, chunks))
    return _dedupe_findings(classify_findings(findings, manifest.intended_findings))


def check_person_attributes(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    findings: list[Finding] = []
    by_person: dict[str, list[Mention]] = defaultdict(list)
    for mention in mentions:
        if mention.kind in {"person", "person-title"} and mention.attributes.get("title"):
            by_person[(mention.canonical or mention.value).lower()].append(mention)

    canon_by_name = {person.name.lower(): person for person in manifest.people}
    for key, person_mentions in by_person.items():
        titles = defaultdict(list)
        for mention in person_mentions:
            titles[_norm_title(mention.attributes["title"])].append(mention)
        canon = canon_by_name.get(key)
        if canon and canon.title:
            canon_title = _norm_title(canon.title)
            for title, title_mentions in titles.items():
                if title != canon_title:
                    bad = title_mentions[0]
                    findings.append(
                        _finding(
                            "person_attribute_conflict",
                            "Person title conflicts with manifest canon",
                            "STANDARD",
                            f"{canon.name} appears with title '{bad.attributes['title']}', but canon says '{canon.title}'.",
                            [bad],
                            {"person": canon.name, "expected_title": canon.title, "observed_title": bad.attributes["title"]},
                        )
                    )
        if len(titles) > 1:
            evidence = [values[0] for values in titles.values()]
            findings.append(
                _finding(
                    "person_attribute_conflict",
                    "Person has multiple observed titles",
                    "STANDARD",
                    f"{evidence[0].canonical or evidence[0].value} appears with multiple titles: "
                    + ", ".join(sorted({item.attributes["title"] for item in evidence})),
                    evidence,
                )
            )
    return findings


def check_role_collisions(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    canon_people = {person.name.lower(): person for person in manifest.people}
    canon_unique_titles = {
        (_norm_title(person.title), _norm_detail(person.org)) for person in manifest.people if person.title and person.org
    }
    declared_unique_titles = {_norm_title(title) for title in manifest.unique_titles}
    file_specs = {spec.path: spec for spec in manifest.files}

    holders: dict[tuple[str, str], dict[str, Mention]] = defaultdict(dict)
    for mention in mentions:
        if mention.kind != "person-title" or not _is_full_person_name(mention.value):
            continue
        title = _norm_title(mention.attributes["title"])
        person_name = mention.canonical or mention.value
        canon = canon_people.get(person_name.lower())
        file_spec = file_specs.get(mention.source.file)
        org = canon.org if canon and canon.org else file_spec.purported_org if file_spec else None
        org_key = _norm_detail(org)
        if not org_key:
            continue
        if title not in declared_unique_titles and (title, org_key) not in canon_unique_titles:
            continue
        holders[(title, org_key)].setdefault(person_name, mention)

    findings: list[Finding] = []
    for (title, org), people in holders.items():
        if len(people) < 2:
            continue
        evidence = list(people.values())
        findings.append(
            _finding(
                "role_collision",
                "Multiple people hold a singular role",
                "STANDARD",
                f"Role '{title}' in '{org}' is held by multiple people: {', '.join(sorted(people))}.",
                evidence,
                {"title": title, "org": org, "people": sorted(people)},
            )
        )
    return findings


def check_unknown_people(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    if not manifest.people:
        return []
    canon_names = {person.name.lower() for person in manifest.people}
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for mention in mentions:
        if mention.kind != "person-title" or not _is_full_person_name(mention.value):
            continue
        name = mention.canonical or mention.value
        if name.lower() in canon_names:
            continue
        key = (name.lower(), mention.attributes["title"].lower())
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            _finding(
                "unknown_person",
                "Person-title mention is absent from canon",
                "DEEP",
                f"{name} appears with title '{mention.attributes['title']}' but is not declared in people canon.",
                [mention],
                {"person": name, "title": mention.attributes["title"]},
            )
        )
    return findings


def check_citation_order(manifest: Manifest, chunks: list[TextChunk]) -> list[Finding]:
    findings: list[Finding] = []
    files = {spec.path: spec for spec in manifest.files}
    dates = {spec.path: parse_manifest_date(spec.purported_date) for spec in manifest.files}

    for edge in manifest.doc_graph:
        source_date = dates.get(edge.source)
        cited_date = dates.get(edge.cites)
        if source_date and cited_date and source_date < cited_date:
            source_ref = _file_spec_to_evidence(files[edge.source], f"purported_date: {source_date.isoformat()}")
            cited_ref = _file_spec_to_evidence(files[edge.cites], f"purported_date: {cited_date.isoformat()}")
            findings.append(
                Finding(
                    "citation_order",
                    "Document predates a declared citation",
                    "STANDARD",
                    "UNINTENDED",
                    f"{edge.source} is dated {source_date.isoformat()} but cites {edge.cites}, dated {cited_date.isoformat()}.",
                    [source_ref, cited_ref],
                    {"from": edge.source, "cites": edge.cites},
                )
            )

    known_dates = {spec.path: parse_manifest_date(spec.purported_date) for spec in manifest.files}
    for chunk in chunks:
        source_date = known_dates.get(chunk.source.file)
        if not source_date:
            continue
        for match in re.finditer(r"\b(?:letter|report|certificate|form|note|memo)\s+of\s+(.{0,30})", chunk.text, re.IGNORECASE):
            parsed = extract_dates(match.group(1), default_year=source_date.year)
            if parsed and source_date < parsed[0][0]:
                findings.append(
                    Finding(
                        "citation_order",
                        "Document appears to cite a future document",
                        "STANDARD",
                        "UNINTENDED",
                        f"{chunk.source.file} is dated {source_date.isoformat()} but refers to '{match.group(0).strip()}'.",
                        [
                            {
                                "file": chunk.source.file,
                                "channel": chunk.source.channel,
                                "location": chunk.source.location,
                                "quote": match.group(0).strip(),
                            }
                        ],
                    )
                )
    return findings


def check_timestamp_monotonicity(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    findings: list[Finding] = []
    timestamps_by_channel: dict[tuple[str, str], list[Mention]] = defaultdict(list)
    chronological = {spec.path: spec.chronological for spec in manifest.files}
    for mention in mentions:
        if mention.kind == "timestamp":
            timestamps_by_channel[(mention.source.file, mention.source.channel)].append(mention)

    for (file_name, channel), values in timestamps_by_channel.items():
        if len(values) < 3:
            continue
        looks_chrono = chronological.get(file_name)
        if looks_chrono is None:
            lower_name = file_name.lower()
            looks_chrono = any(token in lower_name for token in ("log", "export", "study", "record", "minutes", "cmm"))
        if not looks_chrono:
            continue
        parsed = [(mention.attributes["iso"], mention) for mention in values]
        for previous, current in itertools.pairwise(parsed):
            if current[0] < previous[0]:
                findings.append(
                    _finding(
                        "timestamp_monotonicity",
                        "Timestamp sequence is not monotonic",
                        "DEEP",
                        f"{file_name} [{channel}] contains a timestamp that moves backward from {previous[0]} to {current[0]}.",
                        [previous[1], current[1]],
                    )
                )
                break
    return findings


def check_calendar_truth(mentions: list[Mention]) -> list[Finding]:
    return [
        _finding(
            "calendar_truth",
            "Weekday does not match date",
            "GLANCE",
            f"'{mention.value}' does not match calendar date {mention.attributes['date']}.",
            [mention],
        )
        for mention in mentions
        if mention.kind == "weekday-date-mismatch"
    ]


def check_ambiguity_notes(mentions: list[Mention]) -> list[Finding]:
    findings: list[Finding] = []
    for mention in mentions:
        if mention.kind == "ambiguous-date":
            findings.append(
                _finding(
                    "ambiguous_claim",
                    "Ambiguous numeric date",
                    "DEEP",
                    f"'{mention.value}' can be read as either dd/mm/yyyy or mm/dd/yyyy.",
                    [mention],
                )
            )
        elif mention.kind == "ambiguous-person":
            findings.append(
                _finding(
                    "ambiguous_claim",
                    "Ambiguous person alias",
                    "DEEP",
                    f"'{mention.value}' is a single-token alias near another full name; not merged into canon.",
                    [mention],
                    mention.attributes,
                )
            )
    return findings


def check_canon_conflicts(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    findings: list[Finding] = []
    address_mentions = [m for m in mentions if m.kind == "address"]
    for org in manifest.orgs:
        if not org.address:
            continue
        sanctioned = _norm_detail(org.address)
        aliases = [alias.lower() for alias in org.all_names]
        for mention in address_mentions:
            if sanctioned and sanctioned in _norm_detail(mention.value):
                continue
            if any(_near_in_quote(mention.quote, alias, mention.value, limit=60) for alias in aliases):
                findings.append(
                    _finding(
                        "canon_conflict",
                        "Address attributed to canon organisation differs from manifest",
                        "STANDARD",
                        f"{org.name} appears near address '{mention.value}', but canon address is '{org.address}'.",
                        [mention],
                        {"org": org.name, "expected_address": org.address, "observed_address": mention.value},
                    )
                )
    return findings


def check_metadata_claims(manifest: Manifest, chunks: list[TextChunk]) -> list[Finding]:
    findings: list[Finding] = []
    declared = {spec.path: spec for spec in manifest.files}
    for chunk in chunks:
        spec = declared.get(chunk.source.file)
        if not spec or chunk.source.channel != "metadata":
            continue
        lower = chunk.text.lower()
        if spec.purported_author and "author" in lower and spec.purported_author.lower() not in lower:
            findings.append(
                Finding(
                    "metadata_face_claim",
                    "Metadata author may conflict with manifest author",
                    "DEEP",
                    "UNINTENDED",
                    f"{spec.path} has metadata that does not include declared author '{spec.purported_author}'.",
                    [
                        {
                            "file": chunk.source.file,
                            "channel": chunk.source.channel,
                            "location": chunk.source.location,
                            "quote": chunk.text[:240],
                        }
                    ],
                )
            )
    return findings


def check_incidental_repetition(manifest: Manifest, mentions: list[Mention]) -> list[Finding]:
    sanctioned = {_norm_detail(org.address) for org in manifest.orgs if org.address}
    sanctioned |= {_norm_detail(org.phone) for org in manifest.orgs if org.phone}
    findings: list[Finding] = []
    for kind in ("address", "phone"):
        by_value: dict[str, list[Mention]] = defaultdict(list)
        for mention in mentions:
            if mention.kind != kind:
                continue
            normal = _norm_detail(mention.value)
            if not normal or normal in sanctioned:
                continue
            by_value[normal].append(mention)
        for normal, values in by_value.items():
            files = {value.source.file for value in values}
            if len(files) < 2:
                continue
            if not _files_independent(manifest.files, files):
                continue
            findings.append(
                _finding(
                    "incidental_repetition",
                    f"Repeated incidental {kind}",
                    "STANDARD",
                    f"'{values[0].value}' appears in multiple independent files without manifest sanction.",
                    _one_per_file(values),
                    {"normalized_value": normal},
                )
            )
    return findings


def check_phrasing_overlap(manifest: Manifest, chunks: list[TextChunk]) -> list[Finding]:
    findings: list[Finding] = []
    specs_by_file = {spec.path: spec for spec in manifest.files}
    author_by_file = {spec.path: spec.purported_author or spec.purported_org for spec in manifest.files}
    grams: dict[str, list[TextChunk]] = defaultdict(list)
    for chunk in chunks:
        if chunk.source.channel in {"filename", "metadata", "manifest"}:
            continue
        words = re.findall(r"[A-Za-z]{3,}", chunk.text.lower())
        for i in range(max(0, len(words) - 7)):
            gram = " ".join(words[i : i + 8])
            grams[gram].append(chunk)
    for gram, gram_chunks in grams.items():
        files = {chunk.source.file for chunk in gram_chunks}
        if len(files) < 2:
            continue
        if not _files_independent(manifest.files, files):
            continue
        authors = {author_by_file.get(file) for file in files}
        if len({author for author in authors if author}) < 2:
            continue
        orgs = {specs_by_file[file].purported_org for file in files if file in specs_by_file}
        if len({org for org in orgs if org}) == 1:
            continue
        findings.append(
            Finding(
                "phrasing_overlap",
                "Long phrasing overlap across different authors",
                "DEEP",
                "UNINTENDED",
                f"Shared phrase across files: '{gram}'.",
                [
                    {
                        "file": chunk.source.file,
                        "channel": chunk.source.channel,
                        "location": chunk.source.location,
                        "quote": gram,
                    }
                    for chunk in _one_chunk_per_file(gram_chunks)
                ],
            )
        )
        if len(findings) >= 20:
            break
    return findings


def classify_findings(findings: list[Finding], intended_findings: list[str]) -> list[Finding]:
    needles = [item.lower() for item in intended_findings]
    for finding in findings:
        haystack = f"{finding.check} {finding.title} {finding.summary}".lower()
        if any(needle in haystack or haystack in needle for needle in needles):
            finding.classification = "INTENDED"
    return findings


def _finding(
    check: str,
    title: str,
    loudness: str,
    summary: str,
    mentions: list[Mention],
    details: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        check=check,
        title=title,
        loudness=loudness,
        classification="UNINTENDED",
        summary=summary,
        evidence=[
            {
                "file": mention.source.file,
                "channel": mention.source.channel,
                "location": mention.source.location,
                "quote": mention.quote,
            }
            for mention in mentions
        ],
        details=details or {},
    )


def _file_spec_to_evidence(spec: FileSpec, quote: str) -> dict[str, str]:
    return {"file": spec.path, "channel": "manifest", "location": "file declaration", "quote": quote}


def _norm_title(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if normalized == "sqe":
        return "supplier quality engineer"
    return normalized


def _norm_detail(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _is_full_person_name(value: str) -> bool:
    parts = value.split()
    return len(parts) >= 2 and not any(part.endswith(".") for part in parts)


def _files_independent(files: list[FileSpec], observed: set[str]) -> bool:
    specs = {spec.path: spec for spec in files}
    for left, right in itertools.combinations(sorted(observed), 2):
        left_spec = specs.get(left)
        right_spec = specs.get(right)
        if not left_spec or not right_spec:
            return True
        if right in left_spec.independent_of or left in right_spec.independent_of:
            return True
        if (
            left_spec.purported_author
            and right_spec.purported_author
            and left_spec.purported_author == right_spec.purported_author
        ):
            return False
        if left_spec.purported_org and right_spec.purported_org and left_spec.purported_org == right_spec.purported_org:
            return False
    return True


def _one_per_file(values: list[Mention]) -> list[Mention]:
    seen: set[str] = set()
    out: list[Mention] = []
    for value in values:
        if value.source.file not in seen:
            seen.add(value.source.file)
            out.append(value)
    return out


def _one_chunk_per_file(values: list[TextChunk]) -> list[TextChunk]:
    seen: set[str] = set()
    out: list[TextChunk] = []
    for value in values:
        if value.source.file not in seen:
            seen.add(value.source.file)
            out.append(value)
    return out


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    merged: dict[tuple[str, str, str], Finding] = {}
    for finding in findings:
        key = (finding.check, finding.title, finding.summary)
        if key not in merged:
            merged[key] = finding
            continue
        merged[key].evidence.extend(finding.evidence)
    return list(merged.values())


def _near_in_quote(quote: str, left: str, right: str, limit: int) -> bool:
    lower = quote.lower()
    left_index = lower.find(left.lower())
    right_index = lower.find(right.lower())
    return left_index >= 0 and right_index >= 0 and abs(left_index - right_index) <= limit
