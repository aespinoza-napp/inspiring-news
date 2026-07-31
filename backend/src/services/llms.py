from __future__ import annotations

import json
import re
from logging import getLogger
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

from src.config.settings import settings

logger = getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(content: str) -> dict | None:

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = _JSON_BLOCK_PATTERN.search(content)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LLMClient:
    """
    Thin OpenAI-compatible chat-completions client.

    Works unmodified against any provider speaking the OpenAI wire
    format: local Ollama (the default), Groq, OpenRouter, Together.ai,
    or real OpenAI/Azure. Swapping providers is a settings-only change
    (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL) - no code change needed.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: OpenAI | None = None,
    ):
        self.model = model or settings.LLM_MODEL

        self._client = client or OpenAI(
            base_url=base_url or settings.LLM_BASE_URL,
            api_key=api_key or settings.LLM_API_KEY.get_secret_value(),
            timeout=timeout or settings.LLM_TIMEOUT,
        )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 1,
    ) -> dict[str, Any] | None:
        """
        Never raises. Returns None if the provider is unreachable or the
        response can't be coerced into JSON after retries, so callers can
        fall back to a safe default (e.g. an UNVERIFIED verdict).
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(max_retries + 1):

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
            except (APIConnectionError, APITimeoutError, APIError) as exc:
                logger.warning(
                    "LLM call failed (attempt %d): %s",
                    attempt,
                    exc,
                )
                continue

            content = response.choices[0].message.content or ""

            parsed = _parse_json(content)

            if parsed is not None:
                return parsed

            logger.warning(
                "LLM returned non-JSON content on attempt %d",
                attempt,
            )

            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    "Respond with ONLY a valid JSON object, "
                    "no prose, no markdown fences."
                ),
            })

        return None
