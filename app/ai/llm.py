"""Groq (OpenAI-compatible) chat client with strict output validation.

The model's reply is parsed as JSON and validated against Draft. Malformed
or incomplete output raises LLMOutputError, so nothing downstream runs on
bad data.
"""
import json
import re

import httpx
from pydantic import ValidationError

from app import config
from app.ai.schemas import Draft


class LLMOutputError(Exception):
    pass


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_draft(raw: str) -> Draft:
    cleaned = _FENCE.sub("", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"model did not return valid JSON: {exc}") from exc
    try:
        return Draft.model_validate(data)
    except ValidationError as exc:
        raise LLMOutputError(f"model output failed schema validation: {exc}") from exc


class GroqClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.api_key = api_key if api_key is not None else config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        self._client = httpx.Client(
            base_url=base_url or config.LLM_BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
            transport=transport,
        )

    def complete(self, system: str, user: str) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not set in .env")
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def draft(self, system: str, user: str) -> Draft:
        return parse_draft(self.complete(system, user))
