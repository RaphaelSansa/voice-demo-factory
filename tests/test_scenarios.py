from datetime import date, datetime

from conftest import GARAGE, ROOT

from booking_agent.calendar_store import CalendarStore
from booking_agent.scenarios import evaluate, load_scenarios

NOW = datetime(2026, 10, 5, 7, 0)


def store_with_booking():
    store = CalendarStore(GARAGE, today=date(2026, 10, 5))
    store.book("vidange", date(2026, 10, 6), "09:00", "Jeanne", "0612345678", "AB-123-CD", now=NOW)
    return store


def test_passes_when_tools_and_booking_match():
    expect = {
        "tools_called": ["check_availability", "book_appointment"],
        "booking": {"service": "vidange", "date": "2026-10-06", "time": "09:00"},
    }
    assert evaluate(expect, ["check_availability", "book_appointment"], store_with_booking(), "") == []


def test_reports_each_failed_expectation():
    expect = {"tools_called": ["check_availability"], "booking": {"service": "pneus"}, "agent_mentions_any": ["fermé"]}
    failures = evaluate(expect, [], store_with_booking(), "Bonjour")
    assert len(failures) == 3


def test_seeded_bookings_do_not_count_as_new():
    store = store_with_booking()
    seeded = frozenset(a.code for a in store.appointments())
    assert evaluate({"no_booking": True}, [], store, "", seeded) == []
    assert evaluate({"no_booking": True}, [], store, "") != []


def test_reschedule_cancelled_seed_then_new_booking():
    store = store_with_booking()
    seeded = frozenset(a.code for a in store.appointments())
    store.cancel(next(iter(seeded)))
    store.book("vidange", date(2026, 10, 7), "10:00", "Jeanne", "0612345678", "AB-123-CD", now=NOW)
    expect = {"booking": {"service": "vidange", "date": "2026-10-07"}, "cancelled": True}
    assert evaluate(expect, [], store, "", seeded) == []


def test_bundled_scenario_files_are_valid():
    for path in (ROOT / "scenarios").glob("*.yaml"):
        today, scenarios = load_scenarios(path)
        assert today.weekday() == 0 and scenarios
        for sc in scenarios:
            assert sc.caller and sc.expect, sc.name
