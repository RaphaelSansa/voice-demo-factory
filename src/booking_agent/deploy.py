"""Create or update a prospect's agent in the ElevenLabs workspace (idempotent)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from elevenlabs import ElevenLabs

from .agent_builder import conversation_config, tool_requests
from .brief import Brief

log = logging.getLogger(__name__)
STATE_FILE = Path(".agents.json")  # slug -> {agent_id, tool_ids}; git-ignored


def _load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def agent_id_for(slug: str) -> str:
    state = _load_state()
    if slug not in state:
        raise SystemExit(
            f"Aucun agent pour « {slug} ». Lance d'abord : python -m booking_agent deploy briefs/{slug}.yaml"
        )
    return state[slug]["agent_id"]


# Lets text sessions (talk --text, test) switch TTS off: faster and not billed as audio.
PLATFORM_SETTINGS = {"overrides": {"conversation_config_override": {"conversation": {"text_only": True}}}}


def deploy(client: ElevenLabs, brief: Brief) -> str:
    """Re-running after editing a brief updates the same agent instead of creating a new one."""
    state = _load_state()
    entry = state.get(brief.slug, {})
    known: dict[str, str] = entry.get("tool_ids", {})
    tool_ids: dict[str, str] = {}

    for name, request in tool_requests(brief).items():
        if name in known:
            client.conversational_ai.tools.update(known[name], request=request)
            tool_ids[name] = known[name]
            log.info("tool %s updated", name)
        else:
            tool_ids[name] = client.conversational_ai.tools.create(request=request).id
            log.info("tool %s created", name)
        # Save as we go so a later failure never leaves orphan tools behind.
        state[brief.slug] = {**entry, "tool_ids": {**known, **tool_ids}}
        _save_state(state)

    config = conversation_config(brief, list(tool_ids.values()))
    name = f"[demo] {brief.company}"
    if entry.get("agent_id"):
        agent_id = entry["agent_id"]
        client.conversational_ai.agents.update(
            agent_id, conversation_config=config, platform_settings=PLATFORM_SETTINGS, name=name
        )
        log.info("agent updated")
    else:
        agent_id = client.conversational_ai.agents.create(
            conversation_config=config,
            platform_settings=PLATFORM_SETTINGS,
            name=name,
            tags=["demo-factory", brief.sector],
        ).agent_id
        log.info("agent created")

    state[brief.slug] = {"agent_id": agent_id, "tool_ids": tool_ids}
    _save_state(state)
    return agent_id
