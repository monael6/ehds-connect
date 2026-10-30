"""
llm_client.py – Unified LLM provider interface.

Supports:
  openai         – OpenAI API (gpt-4o etc.)
  azure_openai   – Azure OpenAI deployment
  local_ollama   – Local Ollama server

All providers return plain text (the JSON string).
JSON parsing and retry logic lives in extract.py, not here.
Secrets come ONLY from environment variables.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import requests  # used for Ollama


class LLMClient:
    """Provider-agnostic LLM client."""

    def __init__(self) -> None:
        self.provider = os.environ.get("LLM_PROVIDER", "openai").lower()
        self._client: Any = None
        self._model: str = ""
        self._init_provider()

    def _init_provider(self) -> None:
        if self.provider == "openai":
            try:
                from openai import OpenAI  # type: ignore[import]
            except ImportError as exc:
                raise ImportError("pip install openai  to use the openai provider") from exc
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY is not set")
            self._client = OpenAI(api_key=api_key)
            self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")

        elif self.provider == "azure_openai":
            try:
                from openai import AzureOpenAI  # type: ignore[import]
            except ImportError as exc:
                raise ImportError("pip install openai  to use the azure_openai provider") from exc
            self._client = AzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                api_version="2024-02-01",
            )
            self._model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        elif self.provider == "local_ollama":
            self._base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self._model = os.environ.get("OLLAMA_MODEL", "llama3")

        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {self.provider!r}. "
                             "Choose: openai | azure_openai | local_ollama")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> str:
        """Send a chat completion request and return the raw response text."""
        if self.provider in ("openai", "azure_openai"):
            return self._complete_openai(system_prompt, user_prompt, temperature, max_tokens)
        elif self.provider == "local_ollama":
            return self._complete_ollama(system_prompt, user_prompt, temperature, max_tokens)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _complete_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},   # strict JSON output
        )
        return response.choices[0].message.content or ""

    def _complete_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "format": "json",
        }
        resp = requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
