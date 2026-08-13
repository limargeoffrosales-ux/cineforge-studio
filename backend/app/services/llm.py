"""OpenAI-compatible LLM client + lightweight prompt layer.

When OPENAI_API_KEY is set, the pipeline calls this for research, scripts and
SEO; on any failure (network, schema, quota) it transparently falls back to
the deterministic procedural generators, so the studio never blocks on an
upstream provider. This is the extension point for local LLMs (Ollama, vLLM)
— point OPENAI_BASE_URL at them and nothing else changes.
"""
import json
import logging

import httpx

from ..config import settings

log = logging.getLogger("cineforge.llm")


def llm_json(system: str, user: str, temperature: float = 0.8, max_tokens: int = 2400) -> dict | None:
    """Ask the configured model for a JSON object. Returns None on any failure."""
    if not settings.llm_enabled:
        return None
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{settings.OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": settings.OPENAI_MODEL,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001 — provider must never break the pipeline
        log.warning("LLM call failed (%s); falling back to procedural generator", exc)
        return None


def llm_text(system: str, user: str, temperature: float = 0.7) -> str | None:
    if not settings.llm_enabled:
        return None
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{settings.OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": settings.OPENAI_MODEL,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM text call failed (%s)", exc)
        return None
