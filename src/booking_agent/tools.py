"""Client tools exposed to the ElevenLabs agent.

Each handler receives the parameters the LLM chose (plus `tool_call_id`) and
returns a short JSON string. Business errors are returned as data, not raised,
so the agent can explain the problem to the caller and recover.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from .calendar_store import BookingError, CalendarStore

log = logging.getLogger(__name__)

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError as exc:
        raise BookingError("La date doit être au format AAAA-MM-JJ.") from exc


def _ok(**payload: Any) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _minutes(hhmm: str) -> int:
    try:
        hours, minutes = hhmm.split(":")
        return int(hours) * 60 + int(minutes)
    except ValueError as exc:
        raise BookingError("L'heure doit être au format HH:MM.") from exc


def _describe(day: date) -> str:
    return f"{DAYS_FR[day.weekday()]} {day.day:02d}/{day.month:02d}"


class BookingTools:
    """Binds the calendar to tool handlers with the signature ElevenLabs expects."""

    def __init__(self, store: CalendarStore, clock: Callable[[], datetime] = datetime.now) -> None:
        self.store = store
        self.clock = clock

    def handlers(self) -> dict[str, Callable[[dict], str]]:
        return {
            "check_availability": self.check_availability,
            "book_appointment": self.book_appointment,
            "cancel_appointment": self.cancel_appointment,
        }

    def _run(self, name: str, params: dict, fn: Callable[[], str]) -> str:
        safe = {k: v for k, v in params.items() if k not in {"phone", "tool_call_id"}}
        log.info("tool %s %s", name, safe)
        try:
            return fn()
        except BookingError as exc:
            return _error(str(exc))
        except Exception:  # never crash the live call
            log.exception("tool %s failed", name)
            return _error(
                f"Problème technique de mon côté. Proposez que {self.store.brief.company} rappelle le client."
            )

    def check_availability(self, params: dict) -> str:
        def run() -> str:
            day = _parse_day(params.get("date", ""))
            service = self.store.normalize_service(params.get("service", ""))
            slots = self.store.available_slots(service, day, now=self.clock())
            if not slots:
                return _ok(
                    date=_describe(day),
                    service=service,
                    suggested_slots=[],
                    total_available=0,
                    hint="Aucun créneau ce jour-là, proposer un autre jour.",
                )
            # Keep the answer short for voice: a few options spread over the day.
            step = math.ceil(len(slots) / 4)
            answer = {
                "date": _describe(day),
                "service": service,
                "duration_min": self.store.brief.services[service].duration_min,
                "suggested_slots": slots[::step][:4],
                "total_available": len(slots),
            }
            # A specific time asked by the caller must be checked against all slots, not the short list.
            wanted = (params.get("time") or "").strip()
            if wanted:
                answer["requested_time"] = wanted
                answer["requested_time_available"] = wanted in slots
                if wanted not in slots:
                    before = [t for t in slots if _minutes(t) < _minutes(wanted)]
                    after = [t for t in slots if _minutes(t) > _minutes(wanted)]
                    answer["closest_slots"] = before[-1:] + after[:1]
            return _ok(**answer)

        return self._run("check_availability", params, run)

    def book_appointment(self, params: dict) -> str:
        def run() -> str:
            day = _parse_day(params.get("date", ""))
            appt = self.store.book(
                service=params.get("service", ""),
                day=day,
                start=params.get("time", ""),
                customer_name=params.get("customer_name", ""),
                phone=params.get("phone", ""),
                extra=params.get("extra", ""),
                now=self.clock(),
            )
            return _ok(
                confirmation_code=appt.code,
                spelled_code=" ".join(appt.code),
                date=_describe(day),
                time=appt.start_dt.strftime("%H:%M"),
                service=self.store.brief.services[appt.service].label,
            )

        return self._run("book_appointment", params, run)

    def cancel_appointment(self, params: dict) -> str:
        def run() -> str:
            appt = self.store.cancel(params.get("confirmation_code", ""))
            label = self.store.brief.services[appt.service].label
            return _ok(cancelled=appt.code, was=f"{label} le {_describe(appt.start_dt.date())} à {appt.start_dt:%H:%M}")

        return self._run("cancel_appointment", params, run)
