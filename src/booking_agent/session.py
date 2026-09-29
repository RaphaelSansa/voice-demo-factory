"""Run a live conversation with a deployed agent, by voice or by text."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    ClientTools,
    Conversation,
    ConversationInitiationData,
)

from .brief import WEEKDAYS
from .tools import BookingTools


def dynamic_variables(today: date) -> dict:
    return {"today": today.isoformat(), "weekday": WEEKDAYS[today.weekday()]}


@dataclass
class Transcript:
    """Everything that happened in a call: used for the console and for scenario checks."""

    turns: list[tuple[str, str]] = field(default_factory=list)  # (speaker, text)
    tool_calls: list[tuple[str, dict, str]] = field(default_factory=list)  # (name, params, result)
    latencies_ms: list[int] = field(default_factory=list)
    agent_replied: threading.Event = field(default_factory=threading.Event)
    ended: threading.Event = field(default_factory=threading.Event)

    def tools_called(self) -> list[str]:
        return [name for name, _, _ in self.tool_calls]


def _recording(tools: BookingTools, transcript: Transcript, on_event: Callable[[str], None]) -> ClientTools:
    client_tools = ClientTools()
    for name, handler in tools.handlers().items():

        def wrapped(params: dict, _name=name, _handler=handler) -> str:
            result = _handler(params)
            # Keep phone numbers out of transcripts and reports.
            clean = {k: ("***" if k == "phone" else v) for k, v in params.items() if k != "tool_call_id"}
            transcript.tool_calls.append((_name, clean, result))
            on_event(f"  ⚙ {_name}({clean}) -> {result}")
            return result

        client_tools.register(name, wrapped)
    return client_tools


def open_session(
    client: ElevenLabs,
    agent_id: str,
    tools: BookingTools,
    today: date,
    voice: bool,
    on_event: Callable[[str], None] = print,
    mic: bool = True,
) -> tuple[Conversation, Transcript]:
    """voice=False is text only; voice=True plays the agent aloud, with mic=False nobody speaks back."""
    transcript = Transcript()

    def agent_said(text: str) -> None:
        transcript.turns.append(("agent", text))
        on_event(f"{'🤖'} {text}")
        transcript.agent_replied.set()

    def user_said(text: str) -> None:
        if voice and mic:  # typed or scripted lines are already recorded by say()
            transcript.turns.append(("user", text))
            on_event(f"🧑 {text}")

    audio = None
    if voice:
        from .audio import SoundDeviceAudio

        audio = SoundDeviceAudio(mic=mic)

    conversation = Conversation(
        client,
        agent_id,
        requires_auth=True,
        audio_interface=audio,
        config=ConversationInitiationData(
            dynamic_variables=dynamic_variables(today),
            # Text sessions skip TTS entirely (the agent allows this override, see deploy.py).
            conversation_config_override={} if voice else {"conversation": {"text_only": True}},
        ),
        client_tools=_recording(tools, transcript, on_event),
        callback_agent_response=agent_said,
        callback_user_transcript=user_said,
        callback_latency_measurement=transcript.latencies_ms.append,
        callback_end_session=transcript.ended.set,
    )
    conversation.start_session()
    return conversation, transcript


def say(conversation: Conversation, transcript: Transcript, text: str, timeout: float = 30.0) -> str | None:
    """Text mode: send one caller line and wait for the agent's next reply.

    Returns None if the agent does not answer or has already hung up.
    """
    if transcript.ended.is_set():
        return None
    transcript.agent_replied.clear()
    transcript.turns.append(("user", text))
    sent_at = time.monotonic()
    try:
        conversation.send_user_message(text)
    except RuntimeError:  # websocket closed: the agent ended the call
        return None
    if not transcript.agent_replied.wait(timeout):
        return None
    # The agent may speak twice around a tool call; give it a moment to finish.
    while True:
        transcript.agent_replied.clear()
        if not transcript.agent_replied.wait(2.5) or time.monotonic() - sent_at > timeout:
            break
    return transcript.turns[-1][1]


def wait_ready(transcript: Transcript, timeout: float = 15.0) -> bool:
    """The agent speaks first (first_message): wait for it before sending anything."""
    return transcript.agent_replied.wait(timeout)


def fixed_clock(day: date) -> Callable[[], datetime]:
    return lambda: datetime.combine(day, datetime.min.time()).replace(hour=7)
