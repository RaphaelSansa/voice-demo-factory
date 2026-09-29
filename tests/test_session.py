import json
import threading
import time
from datetime import date

from conftest import GARAGE

from booking_agent.calendar_store import CalendarStore
from booking_agent.session import Transcript, _recording, dynamic_variables, fixed_clock, say
from booking_agent.tools import BookingTools


class FakeConversation:
    """Replies like the real agent: a filler line, then the answer after a 'tool call'."""

    def __init__(self, transcript, replies):
        self.transcript, self.replies = transcript, replies

    def send_user_message(self, text):
        def speak():
            for r in self.replies:
                time.sleep(0.05)
                self.transcript.turns.append(("agent", r))
                self.transcript.agent_replied.set()

        threading.Thread(target=speak).start()


def test_say_waits_for_the_agent_to_finish_talking():
    t = Transcript()
    conv = FakeConversation(t, ["Je regarde...", "J'ai neuf heures ou dix heures."])
    assert say(conv, t, "Une vidange demain ?", timeout=10) == "J'ai neuf heures ou dix heures."
    assert t.turns[0] == ("user", "Une vidange demain ?")


def test_client_tools_are_recorded_without_phone_numbers_in_logs():
    today = date(2026, 10, 5)
    t, events = Transcript(), []
    tools = BookingTools(CalendarStore(GARAGE, today=today), clock=fixed_clock(today))
    ct = _recording(tools, t, events.append)
    ct.start()
    done = threading.Event()
    results = []
    ct.execute_tool(
        "check_availability",
        {"tool_call_id": "x", "service": "vidange", "date": "2026-10-06"},
        lambda r: (results.append(r), done.set()),
    )
    assert done.wait(5)
    ct.stop()
    assert results[0]["is_error"] is False and json.loads(results[0]["result"])["ok"]
    assert t.tools_called() == ["check_availability"]


def test_dynamic_variables_give_the_agent_the_date():
    assert dynamic_variables(date(2026, 10, 5)) == {"today": "2026-10-05", "weekday": "lundi"}


def test_phone_numbers_are_masked_in_transcripts():
    today = date(2026, 10, 5)
    t, events = Transcript(), []
    tools = BookingTools(CalendarStore(GARAGE, today=today), clock=fixed_clock(today))
    ct = _recording(tools, t, events.append)
    wrapped = ct.tools["book_appointment"][0]
    wrapped(
        {
            "tool_call_id": "x",
            "service": "vidange",
            "date": "2026-10-06",
            "time": "09:00",
            "customer_name": "Jeanne",
            "phone": "0612345678",
            "extra": "AB-123-CD",
        }
    )
    assert "0612345678" not in " ".join(events) and t.tool_calls[0][1]["phone"] == "***"
