"""Prospect brief: the only thing an SE writes to get a tailored demo agent.

A brief is a small YAML file describing the business (services, opening hours,
tone, FAQ). Everything else, from the agent prompt to the tools and the
calendar rules, is derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

import yaml

WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class BriefError(ValueError):
    pass


@dataclass(frozen=True)
class Service:
    key: str
    label: str
    duration_min: int
    price: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtraField:
    """A business-specific detail to collect at booking (e.g. a licence plate)."""

    key: str
    label: str


@dataclass(frozen=True)
class Brief:
    slug: str
    company: str
    sector: str
    city: str
    agent_name: str
    tone: str
    services: dict[str, Service]
    opening_hours: dict[int, list[tuple[time, time]]]
    faq: dict[str, str] = field(default_factory=dict)
    extra_field: ExtraField | None = None
    max_days_ahead: int = 60
    voice_id: str | None = None
    language: str = "fr"

    def describe_hours(self) -> str:
        parts = []
        for i, name in enumerate(WEEKDAYS):
            ranges = self.opening_hours.get(i)
            if not ranges:
                parts.append(f"{name} : fermé")
            else:
                parts.append(f"{name} : " + ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in ranges))
        return "; ".join(parts)


def _parse_range(value: str) -> tuple[time, time]:
    try:
        start, end = (time.fromisoformat(v.strip()) for v in value.split("-"))
    except ValueError as exc:
        raise BriefError(f"Plage horaire invalide : {value!r} (attendu HH:MM-HH:MM)") from exc
    if start >= end:
        raise BriefError(f"Plage horaire vide : {value!r}")
    return start, end


def load_brief(path: str | Path) -> Brief:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        services = {}
        for key, s in raw["services"].items():
            services[key] = Service(
                key=key,
                label=s.get("label", key),
                duration_min=int(s["duration_min"]),
                price=s.get("price"),
                aliases=tuple(a.lower() for a in s.get("aliases", [])),
            )
        hours: dict[int, list[tuple[time, time]]] = {}
        for day_name, ranges in (raw.get("opening_hours") or {}).items():
            if day_name not in WEEKDAYS:
                raise BriefError(f"Jour inconnu dans opening_hours : {day_name!r}")
            hours[WEEKDAYS.index(day_name)] = [_parse_range(r) for r in ranges or []]
        extra = raw.get("extra_field")
        brief = Brief(
            slug=raw.get("slug", path.stem),
            company=raw["company"],
            sector=raw["sector"],
            city=raw.get("city", ""),
            agent_name=raw.get("agent_name", "Léa"),
            tone=raw.get("tone", "chaleureux et efficace"),
            services=services,
            opening_hours={d: r for d, r in hours.items() if r},
            faq=raw.get("faq") or {},
            extra_field=ExtraField(extra["key"], extra["label"]) if extra else None,
            max_days_ahead=int(raw.get("max_days_ahead", 60)),
            voice_id=raw.get("voice_id"),
            language=raw.get("language", "fr"),
        )
    except KeyError as exc:
        raise BriefError(f"{path.name} : champ obligatoire manquant {exc}") from exc
    if not brief.services:
        raise BriefError(f"{path.name} : au moins un service est requis")
    if not brief.opening_hours:
        raise BriefError(f"{path.name} : aucun horaire d'ouverture")
    return brief
