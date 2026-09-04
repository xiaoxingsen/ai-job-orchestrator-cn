from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


class ModelProvider(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


@dataclass(frozen=True, slots=True)
class OllamaProvider:
    model: str
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

