from __future__ import annotations

import json
import re
import threading
import time
from logging import getLogger
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

from src.config.settings import settings
from src.services.concurrency import LLM, PermitTimeout

logger = getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

# This thread's last complete_json, for LLMClient.last_call().
_LAST_CALL = threading.local()


class LLMUnavailableError(RuntimeError):
    """
    Raised when every attempt failed to reach the provider at all -
    connection refused, timed out, or the API errored before returning a
    body. Deliberately distinct from complete_json returning None (the
    provider answered but never produced valid JSON): a caller collapsing
    both into UNVERIFIED cannot tell "checked, no evidence" from "never
    actually asked", which is exactly what blocked Phase 5 benchmarking
    from telling a wrong answer apart from a dead socket.
    """


def _parse_json(content: str) -> dict | None:
    """
    The JSON *object* in `content`, or None.

    Only an object: `json.loads` is just as happy with `"TRUE"`, `[...]`
    or `true`, and every caller asked for an object and calls `.get` on
    what comes back. A list that wraps the object (`[{...}]`) still
    yields it, through the block search below; anything else is the
    same as no JSON, so `complete_json` retries.
    """

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return parsed

    match = _JSON_BLOCK_PATTERN.search(content)

    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


# English, Spanish and Catalan run 0.2-0.3 tokens per character; a prompt
# the server evaluated at under this many was cut. Measured 2026-10-15 on
# Ollama 0.40.4 with llama3.2:3b and no context configured: 4,000 and
# 12,000 characters arrived as 892 and 2,417 tokens, 30,000 as 2,050 -
# the end of it gone, and nothing in the response but `usage` says so.
_MIN_TOKENS_PER_CHAR = 0.12

# Below this a prompt fits any context; the ratio of a short one is noise.
_MIN_CHARS_TO_JUDGE = 8000


def _warn_if_cut(model: str, chars: int, response) -> None:
    """
    Log when the server evaluated far fewer tokens than the prompt holds.
    Only logged: the answer may still be usable, and the caller cannot
    tell which part was lost. The writer's prompt is the one this
    happens to (docs/decisions/writing.md, "Writing").
    """

    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "prompt_tokens", None)

    if not isinstance(tokens, int) or chars < _MIN_CHARS_TO_JUDGE:
        return

    if tokens < chars * _MIN_TOKENS_PER_CHAR:
        logger.warning(
            "%s evaluated %d tokens of a %d-character prompt: the server probably cut it to "
            "fit the model's context. Ollama serves a small context unless told otherwise "
            "(num_ctx in a Modelfile, or OLLAMA_CONTEXT_LENGTH).",
            model,
            tokens,
            chars,
        )


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

        # Thinking switched off (or set) for the models that need it
        # (LLM_REASONING_EFFORT). Sent as an extra body field, so a
        # provider that does not know it never sees a typed argument.
        effort = settings.LLM_REASONING_EFFORT.get(self.model)
        self._extra = {"extra_body": {"reasoning_effort": effort}} if effort else {}

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
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Returns None if the provider answered but the response can't be
        coerced into JSON after retries, so callers can fall back to a
        safe default (e.g. an UNVERIFIED verdict). Raises
        LLMUnavailableError instead if the *last* attempt never reached
        the provider at all - see that class's docstring for why the two
        are kept apart.

        `max_tokens` caps the answer; None sends no cap, as every caller
        did before the writer (src/services/writer/) needed one. An answer
        cut at the cap is usually unfinished JSON, so it comes back None.

        `timeout`: seconds for the whole call, waiting for the LLM permit
        included, retries too; None is LLM_TIMEOUT per attempt, as before.
        A claim with a deadline passes what it has left, and running out
        is LLMUnavailableError - the claim is "not checked", never judged
        on a half-written answer. Closing the request stops Ollama
        generating, so the permit is not held past it.

        How the call went (permit wait, the call's own seconds, tokens) is
        kept for this thread in `last_call()`.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Only sent when asked for, so every existing call is the request
        # it always was.
        limits = {"max_tokens": max_tokens} if max_tokens is not None else {}

        unreachable = False

        ends_at = None if timeout is None else time.monotonic() + timeout

        call = {"model": self.model, "wait": 0.0, "seconds": 0.0, "promptTokens": None, "completionTokens": None}
        _LAST_CALL.value = call

        for attempt in range(max_retries + 1):

            left = None if ends_at is None else ends_at - time.monotonic()

            if left is not None and left < 1.0:
                # Out of time. Before any answer that is "not checked";
                # after one that was not JSON, it is that answer's failure.
                if attempt == 0:
                    unreachable = True
                break

            asked = time.perf_counter()

            try:
                # Claims are verified concurrently now, so this is where
                # several of them meet. A local Ollama serving one model
                # answers concurrent requests by queueing them anyway -
                # the permit makes that queue explicit and bounded
                # instead of letting every claim hold a socket open.
                with LLM.permit(timeout=left):

                    started = time.perf_counter()
                    call["wait"] = round(call["wait"] + started - asked, 3)

                    per_request = (
                        {"timeout": max(1.0, ends_at - time.monotonic())}
                        if ends_at is not None
                        else {}
                    )

                    try:
                        response = self._client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            response_format={"type": "json_object"},
                            temperature=0.0,
                            **limits,
                            **per_request,
                            **self._extra,
                        )
                    finally:
                        call["seconds"] = round(call["seconds"] + time.perf_counter() - started, 3)

            except PermitTimeout as exc:
                call["wait"] = round(call["wait"] + time.perf_counter() - asked, 3)
                logger.warning("LLM call not started (attempt %d): %s", attempt, exc)
                unreachable = True
                break
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

            usage = getattr(response, "usage", None)
            call["promptTokens"] = getattr(usage, "prompt_tokens", None)
            call["completionTokens"] = getattr(usage, "completion_tokens", None)

            if attempt == 0:
                _warn_if_cut(self.model, len(system_prompt) + len(user_prompt), response)

            content = response.choices[0].message.content or ""

            parsed = _parse_json(content)

            if parsed is not None:
                return parsed

            # Cut at max_tokens: asking again sends the same question at
            # temperature 0 with the cut answer appended, and a model that
            # looped once loops again - another cap's worth of tokens on
            # the process's one LLM permit, for the same None. A verifier
            # call ran into its timeout twice this way (fact081,
            # 2026-10-21: 360 s, where it usually answers in 30).
            if getattr(response.choices[0], "finish_reason", None) == "length":
                logger.warning(
                    "LLM answer cut at max_tokens (%s) on attempt %d; not retried",
                    max_tokens,
                    attempt,
                )
                return None

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
                if ends_at is None or time.monotonic() < ends_at
                else f"{self.model} did not answer within {timeout:.0f} s"
            )

        return None

    @staticmethod
    def last_call() -> dict | None:
        """
        The last `complete_json` on this thread: the model, seconds spent
        waiting for the LLM permit (another claim's call), the call's own
        seconds, and the tokens the server reported (None when it did not).
        Per thread because each claim is checked in its own and asks right
        after its call; a dict, not the response, so nothing holds on to
        the answer.
        """

        return getattr(_LAST_CALL, "value", None)

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
