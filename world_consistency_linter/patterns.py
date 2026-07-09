from __future__ import annotations

import re

from .dates import ambiguous_numeric_dates, extract_dates, extract_timestamps, weekday_mismatches
from .models import Manifest, Mention, TextChunk

TITLE_WORDS = (
    "Supplier Quality Engineer",
    "Quality Manager",
    "Quality Engineer",
    "Operations Director",
    "Manager",
    "Engineer",
    "Director",
    "Inspector",
    "Technician",
    "Supervisor",
    "Coordinator",
    "Lead",
    "SQE",
)
TITLE_RE = "|".join(re.escape(value) for value in sorted(TITLE_WORDS, key=len, reverse=True))
PREFIX_TITLE_WORDS = tuple(
    value for value in TITLE_WORDS if value not in {"Manager", "Engineer", "Director", "Lead"}
)
PREFIX_TITLE_RE = "|".join(re.escape(value) for value in sorted(PREFIX_TITLE_WORDS, key=len, reverse=True))
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d ()-]{7,}\d)\b")
ADDRESS_RE = re.compile(
    r"\b(?:[Uu]nit\s+\d+[A-Z]?|[Ss]uite\s+\d+[A-Z]?|"
    r"\d{1,5}\s+[A-Z][A-Za-z0-9' -]+?\b(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln|"
    r"Drive|Dr|Way|Close|Estate|Park|Court|Ct)\b)"
)
PERSON_RE = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]\.)\s+(?:[A-Z][a-z]+)\b")


def extract_mentions(chunks: list[TextChunk], manifest: Manifest) -> list[Mention]:
    mentions: list[Mention] = []
    for chunk in chunks:
        text = chunk.text
        mentions.extend(_manifest_entity_mentions(chunk, manifest))
        mentions.extend(_person_title_mentions(chunk, manifest))
        mentions.extend(_regex_mentions(chunk, "email", EMAIL_RE))
        mentions.extend(_regex_mentions(chunk, "phone", PHONE_RE))
        mentions.extend(_regex_mentions(chunk, "address", ADDRESS_RE))
        mentions.extend(_candidate_people(chunk, manifest))
        for parsed, raw in extract_dates(text):
            mentions.append(Mention("date", raw, chunk.source, _quote(text, raw), attributes={"iso": parsed.isoformat()}))
        for parsed, raw in extract_timestamps(text):
            mentions.append(
                Mention("timestamp", raw, chunk.source, _quote(text, raw), attributes={"iso": parsed.isoformat()})
            )
        for weekday, parsed, raw in weekday_mismatches(text):
            mentions.append(
                Mention(
                    "weekday-date-mismatch",
                    raw,
                    chunk.source,
                    _quote(text, raw),
                    attributes={"weekday": weekday, "date": parsed.isoformat()},
                )
            )
        for raw in ambiguous_numeric_dates(text):
            mentions.append(Mention("ambiguous-date", raw, chunk.source, _quote(text, raw)))
    return _dedupe_mentions(mentions)


def _manifest_entity_mentions(chunk: TextChunk, manifest: Manifest) -> list[Mention]:
    found: list[Mention] = []
    for person in manifest.people:
        for alias in person.all_names:
            for match in _literal_matches(chunk.text, alias):
                if _is_ambiguous_single_token_alias(chunk.text, match, alias, person.name):
                    found.append(
                        Mention(
                            "ambiguous-person",
                            alias,
                            chunk.source,
                            _quote(chunk.text, alias),
                            attributes={"canon_candidate": person.name},
                        )
                    )
                    continue
                attrs = {}
                title = _title_adjacent(chunk.text, match.start(), match.end())
                if title:
                    attrs["title"] = title
                found.append(
                    Mention("person", alias, chunk.source, _quote(chunk.text, alias), canonical=person.name, attributes=attrs)
                )
    for org in manifest.orgs:
        for alias in org.all_names:
            for _ in _literal_matches(chunk.text, alias):
                found.append(Mention("org", alias, chunk.source, _quote(chunk.text, alias), canonical=org.name))
    for item in manifest.ids:
        for _ in _literal_matches(chunk.text, item.id):
            found.append(Mention("id", item.id, chunk.source, _quote(chunk.text, item.id), canonical=item.id))
    return found


def _person_title_mentions(chunk: TextChunk, manifest: Manifest) -> list[Mention]:
    patterns = [
        re.compile(rf"\b(?P<name>(?:[A-Z][a-z]+|[A-Z]\.)\s+[A-Z][a-z]+)\s*[-,]\s*(?P<title>{TITLE_RE})\b"),
        re.compile(rf"\b(?P<title>{PREFIX_TITLE_RE})\s+(?P<name>(?:[A-Z][a-z]+|[A-Z]\.)\s+[A-Z][a-z]+)\b"),
    ]
    mentions: list[Mention] = []
    stopwords = {word.lower() for word in manifest.stopwords}
    for pattern_index, pattern in enumerate(patterns):
        for match in pattern.finditer(chunk.text):
            if pattern_index == 1 and _looks_like_tail_of_name_title_pair(chunk.text, match.start()):
                continue
            if _name_contains_stopword(match.group("name"), stopwords):
                continue
            mentions.append(
                Mention(
                    "person-title",
                    match.group("name"),
                    chunk.source,
                    _quote(chunk.text, match.group(0)),
                    canonical=match.group("name"),
                    attributes={"title": match.group("title")},
                )
            )
    return mentions


def _candidate_people(chunk: TextChunk, manifest: Manifest) -> list[Mention]:
    mentions: list[Mention] = []
    stopwords = {word.lower() for word in manifest.stopwords}
    for match in PERSON_RE.finditer(chunk.text):
        value = match.group(0)
        if any(token.lower() in stopwords for token in value.split()):
            continue
        mentions.append(Mention("person-candidate", value, chunk.source, _quote(chunk.text, value)))
    return mentions


def _regex_mentions(chunk: TextChunk, kind: str, pattern: re.Pattern[str]) -> list[Mention]:
    return [
        Mention(kind, match.group(0), chunk.source, _quote(chunk.text, match.group(0)))
        for match in pattern.finditer(chunk.text)
    ]


def _literal_matches(text: str, needle: str) -> list[re.Match[str]]:
    return list(re.finditer(rf"(?<!\w){re.escape(needle)}(?!\w)", text, re.IGNORECASE))


def _title_adjacent(text: str, start: int, end: int) -> str | None:
    after = text[end : min(len(text), end + 80)]
    after_match = re.match(rf"^\s*[-,]?\s*(?P<title>{TITLE_RE})\b", after)
    if after_match:
        return after_match.group("title")
    before = text[max(0, start - 80) : start]
    before_match = re.search(rf"\b(?P<title>{TITLE_RE})\s*[-,]?\s*$", before)
    if before_match:
        return before_match.group("title")
    return None


def _is_ambiguous_single_token_alias(text: str, match: re.Match[str], alias: str, canon_name: str) -> bool:
    if len(alias.split()) != 1:
        return False
    for name_match in PERSON_RE.finditer(_window(text, match.start(), match.end(), size=40)):
        observed = name_match.group(0)
        if alias.lower() in observed.lower() and observed.lower() != canon_name.lower():
            return True
    return False


def _looks_like_tail_of_name_title_pair(text: str, title_start: int) -> bool:
    prefix = text[max(0, title_start - 50) : title_start]
    return bool(re.search(r"(?:[A-Z][a-z]+|[A-Z]\.)\s+[A-Z][a-z]+,\s*$", prefix))


def _name_contains_stopword(name: str, stopwords: set[str]) -> bool:
    return any(part.lower().strip(".") in stopwords for part in name.split())


def _window(text: str, start: int, end: int, size: int) -> str:
    return text[max(0, start - size) : min(len(text), end + size)]


def _quote(text: str, needle: str) -> str:
    index = text.lower().find(needle.lower())
    if index < 0:
        return text[:180].replace("\n", " ").strip()
    start = max(0, index - 80)
    end = min(len(text), index + len(needle) + 80)
    return text[start:end].replace("\n", " ").strip()


def _dedupe_mentions(mentions: list[Mention]) -> list[Mention]:
    seen: set[tuple[str, str, str, str, str]] = set()
    out: list[Mention] = []
    for mention in mentions:
        key = (
            mention.kind,
            mention.value.lower(),
            mention.source.file,
            mention.source.channel,
            mention.quote,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(mention)
    return out
