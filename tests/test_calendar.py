from datetime import date, datetime

import pytest
from conftest import GARAGE

from booking_agent.calendar_store import BookingError, CalendarStore

TODAY = date(2026, 10, 5)  # a Monday
NOW = datetime(2026, 10, 5, 7, 0)
TUESDAY = date(2026, 10, 6)


@pytest.fixture
def store(tmp_path):
    return CalendarStore(GARAGE, path=tmp_path / "appointments.json", today=TODAY)


def book(store, start="09:00", service="vidange", day=TUESDAY):
    return store.book(service, day, start, "Jeanne Martin", "06 12 34 56 78", "AB-123-CD", now=NOW)


def test_slots_respect_opening_hours_and_duration(store):
    slots = store.available_slots("revision", TUESDAY, now=NOW)  # 90 min
    assert slots[0] == "08:30"
    assert "11:00" in slots and "11:15" not in slots  # 11:00 + 90 min = 12:30 closing
    assert "14:00" in slots and "17:00" in slots and "17:15" not in slots


def test_saturday_morning_only_and_sunday_closed(store):
    assert store.available_slots("vidange", date(2026, 10, 10), now=NOW)[-1] == "12:30"
    with pytest.raises(BookingError, match="fermé le dimanche"):
        store.available_slots("vidange", date(2026, 10, 11), now=NOW)


def test_booking_blocks_overlapping_slots(store):
    appt = book(store, "09:00", "diagnostic")  # 09:00-10:00
    slots = store.available_slots("vidange", TUESDAY, now=NOW)
    assert "09:00" not in slots and "09:45" not in slots
    assert "08:30" in slots and "10:00" in slots
    assert len(appt.code) == 5


def test_double_booking_refused(store):
    book(store, "09:00")
    with pytest.raises(BookingError, match="plus disponible"):
        book(store, "09:00")


def test_past_slots_today_are_hidden(store):
    slots = store.available_slots("vidange", TODAY, now=datetime(2026, 10, 5, 15, 0))
    assert slots and slots[0] == "15:15"


def test_input_validation(store):
    with pytest.raises(BookingError, match="Service inconnu"):
        store.available_slots("carrosserie", TUESDAY, now=NOW)
    with pytest.raises(BookingError, match="passée"):
        store.available_slots("vidange", date(2026, 10, 1), now=NOW)
    with pytest.raises(BookingError, match="téléphone"):
        store.book("vidange", TUESDAY, "09:00", "Jeanne", "0612", "AB-123-CD", now=NOW)
    with pytest.raises(BookingError, match="immatriculation"):
        store.book("vidange", TUESDAY, "09:00", "Jeanne", "0612345678", "", now=NOW)
    with pytest.raises(BookingError, match="HH:MM"):
        store.book("vidange", TUESDAY, "9h", "Jeanne", "0612345678", "AB-123-CD", now=NOW)


def test_service_aliases(store):
    assert store.normalize_service("Révision") == "revision"
    assert store.normalize_service("changement de pneus") == "pneus"
    assert store.normalize_service("  DIAG ") == "diagnostic"


def test_cancel_frees_slot_and_persists(tmp_path):
    path = tmp_path / "appointments.json"
    store = CalendarStore(GARAGE, path=path, today=TODAY)
    appt = book(store, "09:00")
    reloaded = CalendarStore(GARAGE, path=path, today=TODAY)
    assert reloaded.find(appt.code).extra == "AB-123-CD"
    reloaded.cancel(appt.code.lower())
    assert "09:00" in reloaded.available_slots("vidange", TUESDAY, now=NOW)
    with pytest.raises(BookingError):
        reloaded.find(appt.code)


def test_code_spelled_out_loud_is_found(store):
    appt = book(store, "09:00")
    assert store.find(" - ".join(appt.code).lower()).code == appt.code
