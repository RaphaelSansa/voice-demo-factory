"""Scripted caller scenarios run against the real agent, in text mode.

Each scenario plays a few caller lines, then checks what actually matters for
a booking agent: which tools were called and the final state of the calendar,
not the exact wording the LLM chose.
"""

from __future__ import annotations

import logging
import statistics
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml
from elevenlabs import ElevenLabs

from .brief import Brief
from .calendar_store import CalendarStore
from .session import fixed_clock, open_session, say, wait_ready
from .tools import BookingTools


@dataclass
class Scenario:
    name: str
    caller: list[str]
    expect: dict
    seed: list[dict] = field(default_factory=list)


@dataclass
class Result:
    scenario: Scenario
    passed: bool
    failures: list[str]
    transcript_lines: list[str]
    latencies_ms: list[int]
    network_error: str | None = None  # the websocket dropped: not the agent's fault
    retried: bool = False


def load_scenarios(path: Path) -> tuple[date, list[Scenario]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    today = date.fromisoformat(str(raw["today"]))
    return today, [Scenario(s["name"], s["caller"], s.get("expect", {}), s.get("seed", [])) for s in raw["scenarios"]]


def evaluate(
    expect: dict,
    tools_called: list[str],
    store: CalendarStore,
    agent_text: str,
    seeded_codes: frozenset[str] = frozenset(),
) -> list[str]:
    """Pure function, unit-tested: returns the list of failed expectations."""
    failures = []
    for tool in expect.get("tools_called", []):
        if tool not in tools_called:
            failures.append(f"outil attendu non appelé : {tool}")
    for tool in expect.get("tools_not_called", []):
        if tool in tools_called:
            failures.append(f"outil appelé à tort : {tool}")
    new = [a for a in store.appointments() if a.status == "confirmed" and a.code not in seeded_codes]
    if "booking" in expect:
        want = expect["booking"]
        match = [
            a
            for a in new
            if a.service == want.get("service", a.service)
            and a.start_dt.date().isoformat() == str(want.get("date", a.start_dt.date().isoformat()))
            and a.start_dt.strftime("%H:%M") == want.get("time", a.start_dt.strftime("%H:%M"))
        ]
        if not match:
            failures.append(f"aucune réservation conforme à {want} (créées : {[(a.service, a.start) for a in new]})")
    if expect.get("no_booking") and new:
        failures.append("une réservation a été créée alors qu'elle ne devait pas l'être")
    if expect.get("cancelled") and not any(a.status == "cancelled" for a in store.appointments()):
        failures.append("aucune annulation effectuée")
    words = expect.get("agent_mentions_any", [])
    if words and not any(w.lower() in agent_text.lower() for w in words):
        failures.append(f"l'agent n'a mentionné aucun de : {words}")
    return failures


@contextmanager
def sdk_errors(logger_name: str = "elevenlabs.conversational_ai") -> Iterator[list[str]]:
    """Collect errors the SDK logs from its websocket thread (e.g. keepalive ping timeout)."""
    errors: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            errors.append(record.getMessage())

    handler = _Collect(level=logging.ERROR)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield errors
    finally:
        logger.removeHandler(handler)


CALLER_VOICE = "Eddy (French (France))"  # macOS built-in voice for the scripted caller


def _speak(line: str) -> None:
    subprocess.run(["say", "-v", CALLER_VOICE, line], check=False)


def run_scenario(
    client: ElevenLabs, agent_id: str, brief: Brief, today: date, scenario: Scenario, listen: bool = False
) -> Result:
    """listen=True plays the call aloud: the agent through ElevenLabs TTS, the caller through macOS `say`."""
    clock = fixed_clock(today)
    store = CalendarStore(brief, today=today)
    seeded_codes = frozenset(
        store.book(
            s["service"],
            date.fromisoformat(str(s["date"])),
            s["time"],
            "Client existant",
            "0600000000",
            s.get("extra", "SEED"),
            now=clock(),
        ).code
        for s in scenario.seed
    )
    lines: list[str] = []

    def record(event: str) -> None:
        lines.append(event)
        if listen:
            print(event, flush=True)

    with sdk_errors() as errors:
        conversation, transcript = open_session(
            client, agent_id, BookingTools(store, clock=clock), today, voice=listen, on_event=record, mic=False
        )

        def quiet() -> None:  # let the agent finish speaking before the caller answers
            if listen:
                conversation.audio_interface.wait_until_quiet()

        try:
            if not wait_ready(transcript):
                return Result(scenario, False, ["l'agent n'a pas répondu à l'ouverture"], lines, [], _first(errors))
            for line in scenario.caller:
                quiet()
                if transcript.ended.is_set():
                    record("   (l'agent a raccroché)" if not errors else "   (connexion perdue)")
                    break
                record(f"🧑 {line}")
                if listen:
                    _speak(line)
                if say(conversation, transcript, line) is None and not transcript.ended.is_set():
                    record("   (pas de réponse de l'agent)")
            quiet()
        finally:
            if not transcript.ended.is_set():
                conversation.end_session()
            conversation.wait_for_session_end()

    agent_text = " ".join(t for who, t in transcript.turns if who == "agent")
    failures = evaluate(scenario.expect, transcript.tools_called(), store, agent_text, seeded_codes)
    return Result(scenario, not failures, failures, lines, transcript.latencies_ms, _first(errors))


def _first(errors: list[str]) -> str | None:
    return errors[0] if errors else None


def write_report(brief: Brief, results: list[Result], out_dir: Path = Path("reports")) -> Path:
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{brief.slug}-{datetime.now():%Y%m%d-%H%M}.md"
    passed = sum(r.passed for r in results)
    all_lat = [ms for r in results for ms in r.latencies_ms]
    lat = f"{statistics.median(all_lat):.0f} ms médiane (ping websocket)" if all_lat else "n/a"
    out = [
        f"# Tests de l'agent — {brief.company}",
        "",
        f"**{passed}/{len(results)} scénarios réussis** · latence réseau : {lat}",
        "",
    ]
    for r in results:
        out += [f"## {'✅' if r.passed else '❌'} {r.scenario.name}", ""]
        if r.retried:
            out += ["- relancé une fois après une coupure réseau (pas un échec de l'agent)", ""]
        elif r.network_error:
            out += [f"- coupure réseau pendant l'appel : {r.network_error}", ""]
        out += [f"- {f}" for f in r.failures] + ([""] if r.failures else [])
        out += ["```", *r.transcript_lines, "```", ""]
    path.write_text("\n".join(out), encoding="utf-8")
    return path
