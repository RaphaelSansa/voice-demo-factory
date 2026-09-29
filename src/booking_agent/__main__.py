"""Command line entry point.

python -m booking_agent preview briefs/garage-du-canal.yaml   # offline: show the generated prompt
python -m booking_agent deploy  briefs/garage-du-canal.yaml   # create/update the agent
python -m booking_agent talk    briefs/garage-du-canal.yaml   # speak to it (--text to type)
python -m booking_agent test    briefs/garage-du-canal.yaml   # run the caller scenarios
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from .agent_builder import first_message, system_prompt, tool_requests
from .brief import load_brief


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _client():
    from elevenlabs import ElevenLabs

    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY manquant : copie .env.example en .env et mets ta clé.")
    return ElevenLabs(api_key=key)


def cmd_preview(brief, _args) -> None:
    print(f"--- Premier message ---\n{first_message(brief)}\n")
    print(f"--- Prompt système ---\n{system_prompt(brief)}")
    print("--- Outils ---")
    for name, req in tool_requests(brief).items():
        print(f"{name}: {req.tool_config.parameters.required}")


def cmd_deploy(brief, args) -> None:
    from .deploy import deploy

    agent_id = deploy(_client(), brief)
    print(f"Agent prêt : {agent_id}")
    print(f"Parle-lui : python -m booking_agent talk {args.brief}")


def cmd_talk(brief, args) -> None:
    from .calendar_store import CalendarStore
    from .deploy import agent_id_for
    from .session import open_session, say, wait_ready
    from .tools import BookingTools

    store = CalendarStore(brief, path=Path("data") / f"{brief.slug}.json")
    conversation, transcript = open_session(
        _client(), agent_id_for(brief.slug), BookingTools(store), date.today(), voice=not args.text
    )
    try:
        if args.text:
            wait_ready(transcript)
            while not transcript.ended.is_set():
                line = input("> ").strip()
                if transcript.ended.is_set() or line in {"", "q", "quit"}:
                    break
                if say(conversation, transcript, line) is None and transcript.ended.is_set():
                    print("(l'agent a raccroché)")
        else:
            print("Parle dans le micro. Ctrl+C pour raccrocher.")
            transcript.ended.wait()
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        # The agent may already have hung up (end_call); ending twice crashes the audio driver.
        if not transcript.ended.is_set():
            conversation.end_session()
        conversation_id = conversation.wait_for_session_end()
        print(f"\nConversation {conversation_id} terminée, visible dans l'historique ElevenLabs.")


def cmd_test(brief, args) -> None:
    from .deploy import agent_id_for
    from .scenarios import load_scenarios, run_scenario, write_report

    path = Path(args.scenarios or f"scenarios/{brief.slug}.yaml")
    today, scenarios = load_scenarios(path)
    client, agent_id = _client(), agent_id_for(brief.slug)
    results = []
    for sc in scenarios:
        print(f"▶ {sc.name} ...", end=" ", flush=True)
        result = run_scenario(client, agent_id, brief, today, sc)
        if not result.passed and result.network_error:
            # A dropped websocket says nothing about the agent: replay once, and say so in the report.
            print("coupure réseau, nouvel essai ...", end=" ", flush=True)
            result = run_scenario(client, agent_id, brief, today, sc)
            result.retried = True
        print("OK" if result.passed else "ÉCHEC : " + " ; ".join(result.failures))
        results.append(result)
    report = write_report(brief, results)
    print(f"\n{sum(r.passed for r in results)}/{len(results)} réussis. Rapport : {report}")
    sys.exit(0 if all(r.passed for r in results) else 1)


def main() -> None:
    _load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING"))
    parser = argparse.ArgumentParser(prog="booking_agent", description="Usine à démos d'agents vocaux ElevenLabs")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "deploy", "talk", "test"):
        p = sub.add_parser(name)
        p.add_argument("brief", help="chemin du brief YAML")
        if name == "talk":
            p.add_argument("--text", action="store_true", help="écrire au lieu de parler")
        if name == "test":
            p.add_argument("--scenarios", help="fichier de scénarios (par défaut scenarios/<slug>.yaml)")
    args = parser.parse_args()
    brief = load_brief(args.brief)
    {"preview": cmd_preview, "deploy": cmd_deploy, "talk": cmd_talk, "test": cmd_test}[args.command](brief, args)


if __name__ == "__main__":
    main()
