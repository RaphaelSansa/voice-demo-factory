"""Turn a prospect brief into an ElevenLabs agent definition.

Nothing here calls the network, so the generated config can be inspected with
`preview` and unit-tested offline.
"""

from __future__ import annotations

import os
from datetime import date

from elevenlabs.types import (
    ConversationalConfig,
    LiteralJsonSchemaProperty,
    ObjectJsonSchemaPropertyInput,
    ToolRequestModel,
    ToolRequestModelToolConfig_Client,
)

from .brief import WEEKDAYS, Brief

DEFAULT_LLM = os.getenv("AGENT_LLM", "gemini-2.5-flash")
DEFAULT_TTS_MODEL = "eleven_flash_v2_5"  # multilingual, lowest latency


def _str(description: str, enum: list[str] | None = None) -> LiteralJsonSchemaProperty:
    if enum:
        return LiteralJsonSchemaProperty(type="string", description=description, enum=enum)
    return LiteralJsonSchemaProperty(type="string", description=description)


def tool_requests(brief: Brief) -> dict[str, ToolRequestModel]:
    """Client tools: executed in the caller's process, no public webhook needed."""
    services = list(brief.services)
    booking_props = {
        "service": _str("Clé du service", enum=services),
        "date": _str("Date du rendez-vous, format AAAA-MM-JJ"),
        "time": _str("Heure de début, format HH:MM, choisie parmi les créneaux proposés"),
        "customer_name": _str("Nom et prénom du client"),
        "phone": _str("Numéro de téléphone du client, chiffres uniquement"),
    }
    required = list(booking_props)
    if brief.extra_field:
        booking_props["extra"] = _str(brief.extra_field.label)
        required.append("extra")

    def client_tool(name: str, description: str, props: dict, req: list[str]) -> ToolRequestModel:
        return ToolRequestModel(
            tool_config=ToolRequestModelToolConfig_Client(
                name=f"{name}",
                description=description,
                expects_response=True,
                response_timeout_secs=10,
                parameters=ObjectJsonSchemaPropertyInput(type="object", properties=props, required=req),
            )
        )

    return {
        "check_availability": client_tool(
            "check_availability",
            "Donne quelques créneaux libres pour un service à une date (liste non exhaustive). "
            "Toujours l'appeler avant de proposer un horaire. Si le client demande une heure précise, "
            "passe-la dans `time` : la réponse dit si elle est libre.",
            {
                "service": booking_props["service"],
                "date": booking_props["date"],
                "time": _str("Heure précise demandée par le client, format HH:MM (optionnel)"),
            },
            ["service", "date"],
        ),
        "book_appointment": client_tool(
            "book_appointment",
            "Réserve un créneau après confirmation explicite du client. Renvoie un code de confirmation.",
            booking_props,
            required,
        ),
        "cancel_appointment": client_tool(
            "cancel_appointment",
            "Annule un rendez-vous à partir de son code de confirmation.",
            {"confirmation_code": _str("Code de confirmation à 5 caractères")},
            ["confirmation_code"],
        ),
    }


def system_prompt(brief: Brief) -> str:
    services = "\n".join(
        f"- {s.label} (clé `{s.key}`) : {s.duration_min} min" + (f", {s.price}" if s.price else "")
        for s in brief.services.values()
    )
    faq = "\n".join(f"- {q} : {a}" for q, a in brief.faq.items()) or "- (aucune)"
    extra = f", {brief.extra_field.label}" if brief.extra_field else ""
    return f"""# Rôle
Tu es {brief.agent_name}, l'assistante vocale de « {brief.company} » ({brief.sector}, {brief.city}).
Tu réponds au téléphone pour prendre, déplacer ou annuler des rendez-vous. Ton : {brief.tone}.

# Contexte
Aujourd'hui nous sommes le {{{{today}}}} ({{{{weekday}}}}). Convertis toujours les dates relatives
(« demain », « mardi prochain ») en date AAAA-MM-JJ avant d'appeler un outil.

# Services
{services}

# Horaires
{brief.describe_hours()}

# Informations utiles
{faq}

# Déroulé
1. Comprends le besoin et le service. S'il n'est pas dans la liste, dis-le et propose le plus proche.
2. Demande le jour souhaité, appelle `check_availability`, propose au plus deux ou trois horaires.
   Les créneaux proposés ne sont que des exemples : si le client demande une heure précise,
   rappelle `check_availability` avec `time`.
3. Quand le client choisit, récupère : nom, numéro de téléphone{extra}.
4. Récapitule en une phrase (service, jour, heure) et attends un « oui » clair.
5. Appelle `book_appointment`, puis donne le code de confirmation lettre par lettre.
Pour une annulation, demande le code puis appelle `cancel_appointment`.

# Règles pour la voix
- Une ou deux phrases courtes par tour. Jamais de liste, jamais de markdown.
- Dis les heures à l'oral (« neuf heures trente »), les dates avec le jour (« mardi 6 octobre »).
- Répète le numéro de téléphone par paires pour le confirmer.
- N'invente jamais un créneau ni un prix : seuls les outils et cette fiche font foi.
- N'appelle jamais `book_appointment` sans avoir vérifié l'horaire avec `check_availability` juste avant.
- Si un outil renvoie une erreur, explique-la simplement et propose une alternative.
- Hors sujet ou demande complexe (devis, réclamation) : propose qu'un conseiller rappelle.
- Quand tout est réglé, remercie et termine l'appel avec `end_call`.
"""


def first_message(brief: Brief) -> str:
    return (
        f"{brief.company}, bonjour ! Je suis {brief.agent_name}, l'assistante. "
        "Je peux vous aider à prendre un rendez-vous ?"
    )


def conversation_config(brief: Brief, tool_ids: list[str]) -> ConversationalConfig:
    tts: dict = {"model_id": DEFAULT_TTS_MODEL}
    if brief.voice_id:
        tts["voice_id"] = brief.voice_id
    return ConversationalConfig.model_validate(
        {
            "agent": {
                "first_message": first_message(brief),
                "language": brief.language,
                # Overridden at each session start with the real date (see session.py).
                "dynamic_variables": {
                    "dynamic_variable_placeholders": {
                        "today": date.today().isoformat(),
                        "weekday": WEEKDAYS[date.today().weekday()],
                    }
                },
                "prompt": {
                    "prompt": system_prompt(brief),
                    "llm": DEFAULT_LLM,
                    "temperature": 0.3,
                    "tool_ids": tool_ids,
                    "built_in_tools": {
                        "end_call": {
                            "type": "system",
                            "name": "end_call",
                            "description": "Termine l'appel quand le client n'a plus de demande.",
                            "params": {"system_tool_type": "end_call"},
                        }
                    },
                },
            },
            "tts": tts,
            "turn": {"turn_eagerness": "normal"},
        }
    )
