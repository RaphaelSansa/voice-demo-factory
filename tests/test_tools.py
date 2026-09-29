import json
from datetime import date, datetime

from conftest import GARAGE

from booking_agent.calendar_store import CalendarStore
from booking_agent.tools import BookingTools

NOW = datetime(2026, 10, 5, 7, 0)


def make_tools():
    return BookingTools(CalendarStore(GARAGE, today=date(2026, 10, 5)), clock=lambda: NOW)


def call(tools, name, **params):
    return json.loads(tools.handlers()[name]({"tool_call_id": "t1", **params}))


def test_check_availability_returns_short_list_for_voice():
    res = call(make_tools(), "check_availability", service="vidange", date="2026-10-06")
    assert res["ok"] and res["date"] == "mardi 06/10"
    assert 1 <= len(res["suggested_slots"]) <= 4
    assert res["total_available"] > len(res["suggested_slots"])


def test_full_booking_then_cancel_flow():
    tools = make_tools()
    booked = call(
        tools,
        "book_appointment",
        service="pneus",
        date="2026-10-06",
        time="10:00",
        customer_name="Jeanne Martin",
        phone="+33 6 12 34 56 78",
        extra="AB-123-CD",
    )
    assert booked["ok"] and booked["time"] == "10:00"
    assert booked["spelled_code"].replace(" ", "") == booked["confirmation_code"]
    cancelled = call(tools, "cancel_appointment", confirmation_code=booked["confirmation_code"])
    assert cancelled["ok"] and "changement de pneus" in cancelled["was"]


def test_business_errors_are_returned_not_raised():
    res = call(make_tools(), "check_availability", service="vidange", date="demain")
    assert res == {"ok": False, "error": "La date doit être au format AAAA-MM-JJ."}


def test_unexpected_errors_do_not_crash_the_call():
    tools = make_tools()
    tools.store.available_slots = lambda *a, **k: 1 / 0
    res = call(tools, "check_availability", service="vidange", date="2026-10-06")
    assert res["ok"] is False and "technique" in res["error"]


def test_check_availability_answers_a_specific_time_outside_the_short_list():
    tools = make_tools()
    short = call(tools, "check_availability", service="vidange", date="2026-10-06")["suggested_slots"]
    assert "09:00" not in short
    res = call(tools, "check_availability", service="vidange", date="2026-10-06", time="09:00")
    assert res["requested_time_available"] is True


def test_check_availability_offers_closest_slots_when_time_is_taken():
    res = call(make_tools(), "check_availability", service="vidange", date="2026-10-06", time="12:45")
    assert res["requested_time_available"] is False
    assert res["closest_slots"] == ["12:00", "14:00"]
