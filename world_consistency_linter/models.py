from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOUDNESS_ORDER = {"GLANCE": 3, "STANDARD": 2, "DEEP": 1}


@dataclass(frozen=True)
class SourceRef:
    file: str
    channel: str
    location: str

    def label(self) -> str:
        return f"{self.file} [{self.channel}; {self.location}]"


@dataclass
class TextChunk:
    source: SourceRef
    text: str


@dataclass
class FileSpec:
    path: str
    full_path: Path
    purported_author: str | None = None
    purported_org: str | None = None
    purported_date: str | None = None
    independent_of: list[str] = field(default_factory=list)
    chronological: bool | None = None


@dataclass
class PersonSpec:
    name: str
    aliases: list[str] = field(default_factory=list)
    title: str | None = None
    org: str | None = None

    @property
    def all_names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class OrgSpec:
    name: str
    aliases: list[str] = field(default_factory=list)
    address: str | None = None
    phone: str | None = None

    @property
    def all_names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class IdSpec:
    id: str
    kind: str | None = None
    description: str | None = None


@dataclass
class DocGraphEdge:
    source: str
    cites: str


@dataclass
class Manifest:
    path: Path
    files: list[FileSpec]
    people: list[PersonSpec]
    orgs: list[OrgSpec]
    ids: list[IdSpec]
    doc_graph: list[DocGraphEdge]
    intended_findings: list[str]
    stopwords: set[str]
    unique_titles: set[str]
    raw: dict[str, Any]


@dataclass
class Mention:
    kind: str
    value: str
    source: SourceRef
    quote: str
    canonical: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Finding:
    check: str
    title: str
    loudness: str
    classification: str
    summary: str
    evidence: list[dict[str, str]]
    details: dict[str, Any] = field(default_factory=dict)

    def severity_value(self) -> int:
        return LOUDNESS_ORDER[self.loudness]


@dataclass
class ExtractionResult:
    chunks: list[TextChunk]
    errors: list[str]
    image_only_files: list[str]
    extractor_disagreements: list[str]
