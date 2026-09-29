from pathlib import Path

from booking_agent.brief import load_brief

ROOT = Path(__file__).resolve().parents[1]
GARAGE = load_brief(ROOT / "briefs" / "garage-du-canal.yaml")
SALON = load_brief(ROOT / "briefs" / "atelier-mona.yaml")
