import json
import os
from pathlib import Path

import requests

from src.config import ANTHROPIC_API_URL, ANTHROPIC_MODEL, ROOT

_ENV_LOADED = False


def llm_enabled() -> bool:
    _load_env_file()
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def create_message(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
    _load_env_file()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": os.getenv("ANTHROPIC_MODEL", ANTHROPIC_MODEL),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    blocks = payload.get("content", [])
    return "".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()


def json_completion(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
    text = create_message(system, user, max_tokens=max_tokens, temperature=temperature)
    return json.loads(strip_code_fences(text))


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return cleaned


def _load_env_file():
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            os.environ.setdefault(key, value)

    _ENV_LOADED = True
