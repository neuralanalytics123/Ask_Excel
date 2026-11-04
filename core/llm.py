"""Groq models through Agno, with automatic fallback so the app keeps working."""

import logging
import time

import streamlit as st
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckdb import DuckDbTools
from groq import Groq as GroqClient

from core.config import DEFAULT_MODELS, NON_CHAT_WORDS, Settings
from core.data import TABLE, schema_text

log = logging.getLogger("ai_excel_analyst")
MAX_MODELS_TRIED = 3


@st.cache_resource(ttl=1800, show_spinner=False)
def _live_models(api_key: str) -> list[str]:
    """Chat models this key can really use (refreshed every 30 minutes)."""
    try:
        ids = [m.id for m in GroqClient(api_key=api_key).models.list().data]
    except Exception as e:  # network or key problem; fall back to defaults
        log.warning("Could not list Groq models: %s", type(e).__name__)
        return []
    return [i for i in ids if not any(w in i.lower() for w in NON_CHAT_WORDS)]


def resolve_models(settings: Settings) -> list[str]:
    """Ordered list of models to try: configured ones, else best available."""
    if settings.models:
        return settings.models
    live = _live_models(settings.api_key) if settings.api_key else []
    if not live:
        return DEFAULT_MODELS
    ordered = [m for m in DEFAULT_MODELS if m in live]
    return ordered + [m for m in sorted(live) if m not in ordered]


def build_agent(con, df, api_key: str, model_id: str) -> Agent:
    return Agent(
        model=Groq(id=model_id, api_key=api_key),
        tools=[DuckDbTools(connection=con)],
        instructions=[
            "You are an expert data analyst.",
            f"The data is in a DuckDB table named '{TABLE}'. Always query it with SQL using the DuckDB tools.",
            "Always wrap column names in double quotes because they may contain spaces.",
            "Never invent numbers. If a query fails, fix the SQL and try again.",
            "Only run read-only SELECT queries. Never modify or drop data.",
            "Answer clearly and concisely. Show key numbers, use markdown tables for results, "
            "and mention any assumptions or data quality problems you noticed.",
            f"Table schema:\n{schema_text(df)}",
            f"The table has {len(df)} rows and {len(df.columns)} columns.",
        ],
        markdown=True,
    )


def _kind(e: Exception) -> str:
    t = str(e).lower()
    if "401" in t or "invalid api key" in t or "invalid_api_key" in t:
        return "auth"
    if "model_not_found" in t or "does not exist" in t or "decommission" in t:
        return "model"
    if "429" in t or "rate limit" in t or "rate_limit" in t:
        return "rate"
    if "413" in t or "too large" in t:
        return "size"
    return "other"


_MESSAGES = {
    "auth": "The AI service is not configured correctly. Please contact the site administrator.",
    "rate": "The AI service is very busy right now. Please wait a minute and try again.",
    "size": "That question needs too much data at once. Try a narrower question.",
    "model": "The AI service is temporarily unavailable. Please try again later.",
    "other": "I could not answer that. Try rephrasing the question.",
}


def ask(question: str, history: list[dict], con, df, settings: Settings, models: list[str]) -> tuple[str, str | None]:
    """Ask the AI. Tries up to 3 models. Returns (answer, model_used or None)."""
    context = ""
    recent = history[-settings.history_turns:]
    if recent:
        lines = [f"{m['role'].capitalize()}: {m['content']}" for m in recent]
        context = "Previous conversation (for context only):\n" + "\n".join(lines) + "\n\n"
    prompt = context + "Current question: " + question

    agents = st.session_state.setdefault("agents", {})
    last_kind = "other"
    for model_id in models[:MAX_MODELS_TRIED]:
        try:
            if model_id not in agents:
                agents[model_id] = build_agent(con, df, settings.api_key, model_id)
            response = agents[model_id].run(prompt)
            answer = getattr(response, "content", None) or str(response)
            if answer.strip():
                return answer, model_id
        except Exception as e:
            last_kind = _kind(e)
            log.warning("Model %s failed (%s): %s", model_id, last_kind, type(e).__name__)
            agents.pop(model_id, None)
            if last_kind == "auth":
                break
            time.sleep(0.5)  # brief pause before trying the next model
    return "⚠️ " + _MESSAGES[last_kind], None
