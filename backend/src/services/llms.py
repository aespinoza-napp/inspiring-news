from __future__ import annotations

import json
import re
import time
from logging import getLogger
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

from src.config.settings import settings
from src.services.concurrency import LLM

logger = getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class LLMUnavailableError(RuntimeError):
    """
    Raised when every attempt failed to reach the provider at all -
    connection refused, timed out, or the API errored before returning a
    body. Deliberately distinct from complete_json returning None (the
    provider answered but never produced valid JSON): a caller collapsing
    both into UNVERIFIED cannot tell "checked, no evidence" from "never
    actually asked", which is exactly what blocked Phase 4 benchmarking
    from telling a wrong answer apart from a dead socket.
    """


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
            # The SDK retries timeouts and connection errors twice on its
            # own (DEFAULT_MAX_RETRIES = 2), silently multiplying
            # complete_json's own retry: a slow local model could hold one
            # claim for 6 x LLM_TIMEOUT. Retries are owned by complete_json.
            max_retries=0,
        )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 1,
    ) -> dict[str, Any] | None:
        """
        Returns None if the provider answered but the response can't be
        coerced into JSON after retries, so callers can fall back to a
        safe default (e.g. an UNVERIFIED verdict). Raises
        LLMUnavailableError instead if the *last* attempt never reached
        the provider at all - see that class's docstring for why the two
        are kept apart.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        unreachable = False

        for attempt in range(max_retries + 1):

            try:
                # Claims are verified concurrently now, so this is where
                # several of them meet. A local Ollama serving one model
                # answers concurrent requests by queueing them anyway -
                # the permit makes that queue explicit and bounded
                # instead of letting every claim hold a socket open.
                with LLM.permit():
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
                unreachable = True
                if attempt < max_retries:
                    time.sleep(self._backoff_seconds(attempt))
                continue

            unreachable = False
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

        if unreachable:
            raise LLMUnavailableError(
                f"{self.model} unreachable after {max_retries + 1} attempt(s)"
            )

        return None

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        """
        Exponential backoff before a retry, capped at 5s so one stalled
        claim cannot hold up the whole run. Doubling from a sub-second
        base is enough headroom for Ollama to finish queueing a
        concurrent request without turning a real outage into a long
        silent hang - see LLM_RETRY_BACKOFF_SECONDS.
        """

        return min(settings.LLM_RETRY_BACKOFF_SECONDS * (2 ** attempt), 5.0)
