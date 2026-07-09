from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import DocGraphEdge, FileSpec, IdSpec, Manifest, OrgSpec, PersonSpec


def load_manifest(path: Path) -> Manifest:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")

    base = path.parent
    file_specs: list[FileSpec] = []
    for item in data.get("files", []):
        if isinstance(item, str):
            raw = {"path": item}
        elif isinstance(item, dict):
            raw = item
        else:
            raise ValueError("files entries must be strings or mappings")
        rel = str(raw["path"])
        file_specs.append(
            FileSpec(
                path=rel,
                full_path=(base / rel).resolve(),
                purported_author=_optional_str(raw.get("purported_author")),
                purported_org=_optional_str(raw.get("purported_org")),
                purported_date=_optional_str(raw.get("purported_date")),
                independent_of=[str(value) for value in raw.get("independent_of", [])],
                chronological=raw.get("chronological"),
            )
        )

    entities = data.get("entities") or {}
    people = [
        PersonSpec(
            name=str(item["name"]),
            aliases=[str(alias) for alias in item.get("aliases", [])],
            title=_optional_str(item.get("title")),
            org=_optional_str(item.get("org")),
        )
        for item in entities.get("people", [])
    ]
    orgs = [
        OrgSpec(
            name=str(item["name"]),
            aliases=[str(alias) for alias in item.get("aliases", [])],
            address=_optional_str(item.get("address")),
            phone=_optional_str(item.get("phone")),
        )
        for item in entities.get("orgs", [])
    ]
    ids = [
        IdSpec(
            id=str(item["id"] if isinstance(item, dict) else item),
            kind=_optional_str(item.get("kind")) if isinstance(item, dict) else None,
            description=_optional_str(item.get("description")) if isinstance(item, dict) else None,
        )
        for item in entities.get("ids", [])
    ]
    doc_graph = [
        DocGraphEdge(source=str(item["from"]), cites=str(item["cites"]))
        for item in data.get("doc_graph", [])
    ]
    intended = [str(item) for item in data.get("intended_findings", [])]
    stopwords = {
        "Quality",
        "Operations",
        "Engineering",
        "Manufacturing",
        "Systems",
        "Group",
        *[str(item) for item in data.get("stopwords", [])],
    }
    for org in orgs:
        for name in org.all_names:
            stopwords.update(part for part in name.replace("&", " ").split() if len(part) > 2)
    unique_titles = {str(item) for item in data.get("unique_titles", [])}
    return Manifest(path, file_specs, people, orgs, ids, doc_graph, intended, stopwords, unique_titles, data)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
