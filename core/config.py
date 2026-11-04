"""Central configuration. Secrets come from Streamlit secrets or environment variables only."""

import os
from dataclasses import dataclass

import streamlit as st

# Preferred chat models, best first. The app checks which ones your Groq key can really use.
DEFAULT_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
# Groq models that are not chat models (speech, safety filters, ...)
NON_CHAT_WORDS = ("whisper", "orpheus", "guard", "safeguard", "tts", "embed", "playai")

APP_TITLE = "AI Excel Analyst"


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read a setting from Streamlit secrets, then from environment variables."""
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets file present
        value = None
    if value in (None, ""):
        value = os.environ.get(name)
    return str(value) if value not in (None, "") else default


def _int(name: str, default: int) -> int:
    try:
        return int(get_secret(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    access_code: str | None       # optional password for the whole app
    models: list[str]             # optional fixed model list (comma separated in MODELS)
    max_questions: int            # questions allowed per visitor session
    per_minute: int               # questions per minute, all visitors together
    per_day: int                  # questions per day, all visitors together
    max_rows: int                 # rows kept from an upload
    history_turns: int            # previous chat messages sent as context


def load_settings() -> Settings:
    models = [m.strip() for m in (get_secret("MODELS", "") or "").split(",") if m.strip()]
    return Settings(
        api_key=get_secret("GROQ_API_KEY"),
        access_code=get_secret("APP_ACCESS_CODE"),
        models=models,
        max_questions=_int("MAX_QUESTIONS_PER_SESSION", 40),
        per_minute=_int("MAX_QUESTIONS_PER_MINUTE", 20),
        per_day=_int("MAX_QUESTIONS_PER_DAY", 1500),
        max_rows=_int("MAX_ROWS", 200_000),
        history_turns=_int("HISTORY_TURNS", 6),
    )
