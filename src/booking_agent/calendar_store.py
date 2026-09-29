"""Appointment calendar driven by a prospect brief.

Pure business logic, no ElevenLabs dependency: the voice agent calls into this
module through client tools, and it is unit-tested on its own.
"""

from __future__ import annotations

import json
import secrets
import threading
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .brief import WEEKDAYS, Brief

SLOT_STEP = timedelta(minutes=15)


class BookingError(ValueError):
    """Raised with a message the agent can say back to the caller."""


@dataclass
class Appointment:
    code: str
    service: str
    start: str  # ISO datetime, local time
    end: str
    customer_name: str
    phone: str
    extra: str
    status: str = "confirmed"

    @property
    def start_dt(self) -> datetime:
        return datetime.fromisoformat(self.start)

    @property
    def end_dt(self) -> datetime:
        return datetime.fromisoformat(self.end)


class CalendarStore:
    """Thread-safe calendar persisted to a JSON file (or kept in memory)."""

    def __init__(self, brief: Brief, path: Path | None = None, today: date | None = None) -> None:
        self.brief = brief
        self._path = path
        self._today = today
        self._lock = threading.Lock()
        self._appointments: dict[str, Appointment] = {}
        if path and path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._appointments = {a["code"]: Appointment(**a) for a in raw}

    # ---------- helpers ----------

    def today(self) -> date:
        return self._today or date.today()

    def _save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(a) for a in self._appointments.values()]
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _fold(text: str) -> str:
        text = unicodedata.normalize("NFKD", (text or "").strip().lower())
        return "".join(c for c in text if not unicodedata.combining(c))

    def normalize_service(self, service: str) -> str:
        wanted = self._fold(service)
        for s in self.brief.services.values():
            names = {self._fold(s.key), self._fold(s.label), *(self._fold(a) for a in s.aliases)}
            if wanted in names:
                return s.key
        offered = ", ".join(s.label for s in self.brief.services.values())
        raise BookingError(f"Service inconnu : « {service} ». Services proposés : {offered}.")

    def _check_date(self, day: date) -> None:
        if day < self.today():
            raise BookingError("Cette date est déjà passée.")
        if day > self.today() + timedelta(days=self.brief.max_days_ahead):
            raise BookingError(f"On ne prend pas de rendez-vous à plus de {self.brief.max_days_ahead} jours.")
        if day.weekday() not in self.brief.opening_hours:
            raise BookingError(f"{self.brief.company} est fermé le {WEEKDAYS[day.weekday()]}.")

    def _busy(self, day: date) -> list[tuple[datetime, datetime]]:
        return [
            (a.start_dt, a.end_dt)
            for a in self._appointments.values()
            if a.status == "confirmed" and a.start_dt.date() == day
        ]

    # ---------- public API ----------

    def available_slots(self, service: str, day: date, now: datetime | None = None) -> list[str]:
        """Start times (HH:MM) where the service fits in opening hours without overlap."""
        service = self.normalize_service(service)
        self._check_date(day)
        duration = timedelta(minutes=self.brief.services[service].duration_min)
        busy = self._busy(day)
        now = now or datetime.now()
        slots: list[str] = []
        for open_t, close_t in self.brief.opening_hours[day.weekday()]:
            cursor = datetime.combine(day, open_t)
            close = datetime.combine(day, close_t)
            while cursor + duration <= close:
                end = cursor + duration
                overlaps = any(cursor < b_end and end > b_start for b_start, b_end in busy)
                if not overlaps and cursor > now:
                    slots.append(cursor.strftime("%H:%M"))
                cursor += SLOT_STEP
        return slots

    def book(
        self,
        service: str,
        day: date,
        start: str,
        customer_name: str,
        phone: str,
        extra: str = "",
        now: datetime | None = None,
    ) -> Appointment:
        service = self.normalize_service(service)
        name = (customer_name or "").strip()
        phone_digits = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
        extra_clean = (extra or "").strip()
        if not name:
            raise BookingError("Il me faut le nom du client.")
        if len(phone_digits.lstrip("+")) < 9:
            raise BookingError("Le numéro de téléphone semble incomplet.")
        if self.brief.extra_field and not extra_clean:
            raise BookingError(f"Il me faut : {self.brief.extra_field.label}.")
        try:
            start_t = datetime.strptime(start.strip(), "%H:%M").time()
        except ValueError as exc:
            raise BookingError("L'heure doit être au format HH:MM, par exemple 09:30.") from exc

        with self._lock:
            if start_t.strftime("%H:%M") not in self.available_slots(service, day, now=now):
                raise BookingError("Ce créneau n'est plus disponible. Proposez un autre horaire.")
            start_dt = datetime.combine(day, start_t)
            end_dt = start_dt + timedelta(minutes=self.brief.services[service].duration_min)
            code = self._new_code()
            appt = Appointment(
                code=code,
                service=service,
                start=start_dt.isoformat(timespec="minutes"),
                end=end_dt.isoformat(timespec="minutes"),
                customer_name=name,
                phone=phone_digits,
                extra=extra_clean,
            )
            self._appointments[code] = appt
            self._save()
            return appt

    def appointments(self) -> list[Appointment]:
        return list(self._appointments.values())

    def find(self, code: str) -> Appointment:
        appt = self._appointments.get("".join(c for c in (code or "").upper() if c.isalnum()))
        if not appt or appt.status != "confirmed":
            raise BookingError("Je ne trouve aucun rendez-vous actif avec ce code.")
        return appt

    def cancel(self, code: str) -> Appointment:
        with self._lock:
            appt = self.find(code)
            appt.status = "cancelled"
            self._save()
            return appt

    def _new_code(self) -> str:
        # Short, easy to spell out loud: no 0/O or 1/I.
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(5))
            if code not in self._appointments:
                return code
