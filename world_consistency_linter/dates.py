from __future__ import annotations

import re
from datetime import date, datetime

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DATE_PATTERNS = [
    re.compile(r"\b(?P<y>20\d{2})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})\b"),
    re.compile(r"\b(?P<d>\d{1,2})[-/](?P<m>\d{1,2})[-/](?P<y>20\d{2})\b"),
    re.compile(
        r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(?P<y>20\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?(?:,\s*)?(?P<y>20\d{2})\b",
        re.IGNORECASE,
    ),
]

TIMESTAMP_PATTERN = re.compile(
    r"\b(?P<date>20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/20\d{2})"
    r"(?:[ T]+|\s*\|\s*|\s*,\s*)(?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?\b"
)


def parse_manifest_date(value: str | None) -> date | None:
    if not value:
        return None
    parsed = parse_first_date(str(value))
    return parsed[0] if parsed else None


def parse_first_date(text: str, default_year: int | None = None) -> tuple[date, str] | None:
    dates = extract_dates(text, default_year=default_year)
    if not dates:
        return None
    return dates[0]


def extract_dates(text: str, default_year: int | None = None) -> list[tuple[date, str]]:
    found: list[tuple[int, date, str]] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            parsed = _date_from_match(match)
            if parsed:
                found.append((match.start(), parsed, match.group(0)))

    if default_year:
        short_month = re.compile(
            r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+"
            r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b",
            re.IGNORECASE,
        )
        for match in short_month.finditer(text):
            try:
                parsed = date(default_year, MONTHS[match.group("mon").lower()], int(match.group("d")))
            except ValueError:
                continue
            found.append((match.start(), parsed, match.group(0)))
    found.sort(key=lambda item: item[0])
    return [(parsed, raw) for _, parsed, raw in found]


def extract_timestamps(text: str) -> list[tuple[datetime, str]]:
    values: list[tuple[int, datetime, str]] = []
    for match in TIMESTAMP_PATTERN.finditer(text):
        date_part = parse_first_date(match.group("date"))
        if not date_part:
            continue
        parsed_date, _ = date_part
        try:
            parsed = datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
                int(match.group("h")),
                int(match.group("min")),
                int(match.group("s") or 0),
            )
        except ValueError:
            continue
        values.append((match.start(), parsed, match.group(0)))
    values.sort(key=lambda item: item[0])
    return [(parsed, raw) for _, parsed, raw in values]


def weekday_mismatches(text: str) -> list[tuple[str, date, str]]:
    pattern = re.compile(
        r"\b(?P<weekday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"
        r"[, ]{0,4}(?P<tail>.{0,40})",
        re.IGNORECASE,
    )
    mismatches: list[tuple[str, date, str]] = []
    for match in pattern.finditer(text):
        parsed = parse_first_date(match.group("tail"))
        if parsed and WEEKDAYS[match.group("weekday").lower()] != parsed[0].weekday():
            mismatches.append((match.group("weekday"), parsed[0], match.group(0).strip()))
    return mismatches


def ambiguous_numeric_dates(text: str) -> list[str]:
    pattern = re.compile(r"\b(?P<a>\d{1,2})/(?P<b>\d{1,2})/(?P<y>20\d{2})\b")
    values: list[str] = []
    for match in pattern.finditer(text):
        a = int(match.group("a"))
        b = int(match.group("b"))
        if 1 <= a <= 12 and 1 <= b <= 12 and a != b:
            values.append(match.group(0))
    return values


def _date_from_match(match: re.Match[str]) -> date | None:
    groups = match.groupdict()
    try:
        year = int(groups["y"])
        month = MONTHS[groups["mon"].lower()] if groups.get("mon") else int(groups["m"])
        day = int(groups["d"])
        return date(year, month, day)
    except (KeyError, TypeError, ValueError):
        return None
