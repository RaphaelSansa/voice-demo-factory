import pytest
from conftest import GARAGE, SALON

from booking_agent.agent_builder import conversation_config, system_prompt, tool_requests
from booking_agent.brief import BriefError, load_brief


def test_config_is_valid_for_the_sdk_and_references_tools():
    cfg = conversation_config(GARAGE, ["tool_a", "tool_b", "tool_c"]).model_dump(exclude_none=True)
    prompt = cfg["agent"]["prompt"]
    assert prompt["tool_ids"] == ["tool_a", "tool_b", "tool_c"]
    assert prompt["built_in_tools"]["end_call"]["params"]["system_tool_type"] == "end_call"
    assert cfg["agent"]["language"] == "fr"
    assert cfg["tts"]["model_id"] == "eleven_flash_v2_5"


def test_prompt_is_generated_from_the_brief():
    p = system_prompt(GARAGE)
    assert "Garage du Canal" in p and "{{today}}" in p
    assert "vidange" in p and "79 €" in p and "dimanche : fermé" in p
    assert "plaque d'immatriculation" in p
    assert "plaque" not in system_prompt(SALON)


def test_extra_field_only_required_when_the_brief_asks_for_it():
    garage = tool_requests(GARAGE)["book_appointment"].tool_config.parameters
    salon = tool_requests(SALON)["book_appointment"].tool_config.parameters
    assert "extra" in garage.required and "extra" not in salon.required
    assert garage.properties["service"].enum == ["vidange", "pneus", "diagnostic", "revision"]


def test_brief_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "company: X\nsector: Y\nservices: {a: {duration_min: 30}}\nopening_hours: {lundi: ['18:00-09:00']}\n"
    )
    with pytest.raises(BriefError, match="vide"):
        load_brief(bad)
    bad.write_text("company: X\nservices: {a: {duration_min: 30}}\n")
    with pytest.raises(BriefError, match="sector"):
        load_brief(bad)
