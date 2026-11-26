from __future__ import annotations

import json
import re
import threading
import time
from logging import getLogger
from typing import Any
from urllib.parse import urlparse

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from src.config.settings import settings
from src.services.concurrency import LLM, PermitTimeout

logger = getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

# A hosted provider's 429 says when to ask again (`retry-after`); Groq's
# free plan allows 8,000 tokens a minute per model, a claim's per-source
# calls ~3,500 (2026-10-29), so two claims at once meet it every minute.
# Waited out, not counted as a failure: a refused call is a source never
# weighed, a verdict the limit made rather than the model. A wait longer
# than this is a daily cap, not a minute's - failing then is the answer.
RATE_LIMIT_MAX_WAIT_SECONDS = 60.0
RATE_LIMIT_MAX_WAITS = 10

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


def _is_model_loop(exc: Exception) -> bool:
    """Ollama's answer to a model repeating itself, audit 2026-10-16: "token repeat limit reached"."""

    return "repeat limit" in str(exc).lower()


# ----------------------------------------------------------------------
# Groq first (2026-11-25, the author's decision)
# ----------------------------------------------------------------------
#
# In the API process a call goes to Groq's hosted model when a key is
# configured (GROQ_API_KEY) and Groq is answering, and to the configured
# local model when it is not. Only there: src/main.py turns it on at
# startup, so the evaluation harness, the experiments and every script ask
# exactly the model they name - a run that switched models halfway would
# measure neither. docs/decisions/evaluation.md, "Groq first".
_GROQ_FIRST = False

# How long Groq is left alone after a failure that would repeat, so every
# call does not pay to find out again. For one model (a model withdrawn, a
# day's cap reached) or the whole key, "*" (a refused key, no network, the
# service down). A failure of one request - too large for the free plan's
# tokens a minute, JSON that failed Groq's own validation - pauses nothing:
# the next one may fit.
GROQ_PAUSE_UNREACHABLE_SECONDS = 300.0
GROQ_PAUSE_SERVER_ERROR_SECONDS = 60.0
GROQ_PAUSE_REFUSED_SECONDS = 3600.0
# A 429 past the minute's waits without a retry-after: an hour, rather than
# asking again on every call of a day whose cap is spent.
GROQ_PAUSE_CAPPED_SECONDS = 3600.0

_GROQ_PAUSES: dict[str, tuple[float, str]] = {}
_GROQ_LOCK = threading.Lock()


def ask_groq_first(enabled: bool = True) -> None:
    """Turn Groq first on for this process (src/main.py), or off."""

    global _GROQ_FIRST
    _GROQ_FIRST = enabled


def groq_first() -> bool:

    return _GROQ_FIRST


def groq_model_for(model: str) -> str | None:
    """
    The Groq model asked in place of the local `model`: GROQ_MODELS' entry
    for it, else GROQ_MODEL. An empty name keeps that model local.
    """

    return settings.GROQ_MODELS.get(model, settings.GROQ_MODEL) or None


def groq_key() -> str | None:

    key = settings.GROQ_API_KEY.get_secret_value().strip() if settings.GROQ_API_KEY else ""

    return key or None


def asked_first(model: str) -> str:
    """
    The model a call for the local `model` goes to first, in this process
    now: its Groq model under Groq first, unless Groq is paused for it;
    else `model`. For a record made before any call (the lake's lineage).
    """

    groq = groq_model_for(model)

    if (
        not _GROQ_FIRST
        or groq is None
        or groq_key() is None
        or _host(settings.LLM_BASE_URL) == _host(settings.GROQ_BASE_URL)
        or groq_paused(groq)
    ):
        return model

    return groq


def groq_paused(model: str) -> str | None:
    """Why Groq is not being asked for `model` now, or None when it is."""

    now = time.monotonic()

    with _GROQ_LOCK:
        for scope in ("*", model):
            until, reason = _GROQ_PAUSES.get(scope, (0.0, ""))
            if until > now:
                return reason
            _GROQ_PAUSES.pop(scope, None)

    return None


def reset_groq_pauses() -> None:

    with _GROQ_LOCK:
        _GROQ_PAUSES.clear()


class _GroqUnavailable(Exception):
    """Groq could not answer this call: ask the local model instead."""

    def __init__(self, reason: str, scope: str | None = None, pause: float = 0.0):
        super().__init__(reason)
        self.reason = reason
        self.scope = scope
        self.pause = pause


def _groq_failure(exc: Exception, model: str) -> _GroqUnavailable:
    """What a failed Groq call means: for how long, and for what, to leave it alone."""

    if isinstance(exc, RateLimitError):
        try:
            wait = float(exc.response.headers.get("retry-after", ""))
        except (AttributeError, ValueError):
            wait = None
        if wait is not None and wait > 0:
            return _GroqUnavailable(f"rate limit, retry after {wait:.0f} s", model, wait)
        return _GroqUnavailable("rate limit", model, GROQ_PAUSE_CAPPED_SECONDS)

    # APITimeoutError is one of these.
    if isinstance(exc, APIConnectionError):
        return _GroqUnavailable(f"unreachable ({type(exc).__name__})", "*", GROQ_PAUSE_UNREACHABLE_SECONDS)

    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    detail = f"{status}{f', {code}' if code else ''}"

    if status in (401, 403):
        return _GroqUnavailable(f"refused the key ({detail})", "*", GROQ_PAUSE_REFUSED_SECONDS)

    if status == 404:
        return _GroqUnavailable(f"does not serve {model} ({detail})", model, GROQ_PAUSE_REFUSED_SECONDS)

    if isinstance(status, int) and status >= 500:
        return _GroqUnavailable(f"server error ({detail})", "*", GROQ_PAUSE_SERVER_ERROR_SECONDS)

    return _GroqUnavailable(f"refused this request ({detail or type(exc).__name__})")


class LLMClient:
    """
    Thin OpenAI-compatible chat-completions client.

    Works unmodified against any provider speaking the OpenAI wire
    format: local Ollama (the default), Groq, OpenRouter, Together.ai,
    or real OpenAI/Azure. Swapping providers is a settings-only change
    (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL) - no code change needed.

    In the API process, Groq first (above): each call asks Groq's model
    for this one (`groq_model_for`) and, when Groq cannot answer, this
    one. Only for a client built from the settings: one given its own
    endpoint or transport (a test's fake, the harness's headless Claude, a
    script naming its server) is asked as given.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: OpenAI | None = None,
        groq_client: OpenAI | None = None,
    ):
        # The model the settings (or the caller) name: the one asked when
        # Groq is not.
        self.local_model = model or settings.LLM_MODEL
        self._timeout = timeout or settings.LLM_TIMEOUT

        # Thinking switched off (or set) for the models that need it
        # (LLM_REASONING_EFFORT). Sent as an extra body field, so a
        # provider that does not know it never sees a typed argument.
        self._extra = _reasoning_effort(self.local_model)

        # Room for the reasoning on top of every cap (LLM_REASONING_TOKENS).
        self._reasoning_tokens = settings.LLM_REASONING_TOKENS.get(self.local_model, 0)

        self._client = client or OpenAI(
            base_url=base_url or settings.LLM_BASE_URL,
            api_key=api_key or settings.LLM_API_KEY.get_secret_value(),
            timeout=self._timeout,
            # The SDK retries timeouts and connection errors twice on its
            # own (DEFAULT_MAX_RETRIES = 2), silently multiplying
            # complete_json's own retry: a slow local model could hold one
            # claim for 6 x LLM_TIMEOUT. Retries are owned by complete_json.
            max_retries=0,
        )

        pinned = base_url is not None or api_key is not None or client is not None
        # Already Groq (a harness run pointed LLM_BASE_URL at it): nothing
        # to ask first.
        local_is_groq = _host(settings.LLM_BASE_URL) == _host(settings.GROQ_BASE_URL)
        eligible = groq_client is not None or (not pinned and not local_is_groq and groq_key() is not None)

        self._groq_model = groq_model_for(self.local_model) if eligible else None
        # A Groq transport given (a test's fake) is asked whatever the
        # process says; one built here only in a process that asks Groq first.
        self._groq_given = groq_client is not None
        self._groq_client = groq_client
        self._groq_lock = threading.Lock()

        # The model this thread's last call went to, for `model`.
        self._thread = threading.local()

    @property
    def model(self) -> str:
        """
        The model this thread's last call through this client went to - the
        one that answered, or the last one tried when none did - and before
        any, the one it would ask first. What a draft, a review or a
        selection records as the model that made it, read after its call.
        """

        asked = getattr(self._thread, "model", None)

        if asked:
            return asked

        return self._groq_model if self._asks_groq() is None else self.local_model

    def _asks_groq(self) -> str | None:
        """
        None when this call goes to Groq first; otherwise why not, or ""
        when Groq first does not apply to this client at all.
        """

        if not self._groq_model or not (_GROQ_FIRST or self._groq_given):
            return ""

        paused = groq_paused(self._groq_model)

        return f"paused, {paused}" if paused else None

    def _groq(self) -> OpenAI:

        with self._groq_lock:
            if self._groq_client is None:
                self._groq_client = OpenAI(
                    base_url=settings.GROQ_BASE_URL,
                    api_key=groq_key() or "",
                    timeout=self._timeout,
                    max_retries=0,
                )

        return self._groq_client

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

        Groq first (above): Groq is asked once, and a call it could not
        answer - unreachable, refused, capped - goes to the local model
        with whatever time is left. One it answered stays its answer,
        JSON or not: Groq was there, and the model's reply is the reply.

        How the call went (permit wait, the call's own seconds, tokens) is
        kept for this thread in `last_call()`; with Groq first, also who
        answered (`provider`) and why Groq did not (`fallback`).
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        ends_at = None if timeout is None else time.monotonic() + timeout

        call = {"model": self.local_model, "wait": 0.0, "seconds": 0.0, "promptTokens": None, "completionTokens": None}
        _LAST_CALL.value = call

        not_groq = self._asks_groq()

        if not_groq is None:

            call["model"] = self._groq_model
            call["provider"] = "groq"
            self._thread.model = self._groq_model

            try:
                return self._ask(
                    self._groq(), self._groq_model, _reasoning_effort(self._groq_model),
                    settings.LLM_REASONING_TOKENS.get(self._groq_model, 0),
                    list(messages), max_retries, max_tokens, timeout, ends_at, call, groq=True,
                )
            except _GroqUnavailable as exc:
                if exc.scope and exc.pause > 0:
                    with _GROQ_LOCK:
                        _GROQ_PAUSES[exc.scope] = (time.monotonic() + exc.pause, exc.reason)
                logger.warning(
                    "Groq could not answer (%s: %s); asking %s instead",
                    self._groq_model, exc.reason, self.local_model,
                )
                not_groq = exc.reason

        if not_groq:
            call["provider"] = "local"
            call["fallback"] = f"Groq: {not_groq}"

        call["model"] = self.local_model
        call["promptTokens"] = call["completionTokens"] = None
        self._thread.model = self.local_model

        return self._ask(
            self._client, self.local_model, self._extra, self._reasoning_tokens,
            messages, max_retries, max_tokens, timeout, ends_at, call,
        )

    def _ask(
        self,
        client,
        model: str,
        extra: dict,
        reasoning_tokens: int,
        messages: list[dict],
        max_retries: int,
        max_tokens: int | None,
        timeout: float | None,
        ends_at: float | None,
        call: dict,
        groq: bool = False,
    ) -> dict[str, Any] | None:
        """
        complete_json against one endpoint. `groq`: Groq first's attempt,
        where a failure to get an answer is not retried here but raised as
        _GroqUnavailable, for the local model to answer instead.
        """

        system_prompt, user_prompt = messages[0]["content"], messages[1]["content"]

        # Only sent when asked for, so every existing call is the request
        # it always was.
        limits = {"max_tokens": max_tokens + reasoning_tokens} if max_tokens is not None else {}

        unreachable = False

        for attempt in range(max_retries + 1):

            left = None if ends_at is None else ends_at - time.monotonic()

            if left is not None and left < 1.0:
                # Out of time. Before any answer that is "not checked";
                # after one that was not JSON, it is that answer's failure.
                if attempt == 0:
                    unreachable = True
                break

            asked = time.perf_counter()
            rate_limited = 0

            try:
                while True:
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
                                response = client.chat.completions.create(
                                    model=model,
                                    messages=messages,
                                    response_format={"type": "json_object"},
                                    temperature=0.0,
                                    **limits,
                                    **per_request,
                                    **extra,
                                )
                            finally:
                                call["seconds"] = round(call["seconds"] + time.perf_counter() - started, 3)
                        break
                    except RateLimitError as exc:
                        # Outside the permit: the wait is the provider's,
                        # and holding the permit through it would stall
                        # every other claim's call behind this one.
                        wait = self._rate_limit_wait(exc, ends_at)
                        rate_limited += 1
                        if wait is None or rate_limited > RATE_LIMIT_MAX_WAITS:
                            if groq:
                                raise _groq_failure(exc, model) from exc
                            raise
                        logger.warning("LLM rate-limited; asking again in %.1f s", wait)
                        time.sleep(wait)
                        call["wait"] = round(call["wait"] + wait, 3)
                        asked = time.perf_counter()
                        left = None if ends_at is None else ends_at - time.monotonic()

            except PermitTimeout as exc:
                # Out of time waiting for the permit: the local model would
                # wait for the same one, so this is "not checked" either way.
                call["wait"] = round(call["wait"] + time.perf_counter() - asked, 3)
                logger.warning("LLM call not started (attempt %d): %s", attempt, exc)
                unreachable = True
                break
            except (APIConnectionError, APITimeoutError, APIError) as exc:

                if groq:
                    raise _groq_failure(exc, model) from exc

                logger.warning(
                    "LLM call failed (attempt %d): %s",
                    attempt,
                    exc,
                )

                # The model answered, in a loop, and Ollama cut it off with
                # a 500. It was reached, so this is an unusable answer and
                # not "LLM provider was unreachable": the same question
                # would loop the same way, so it is not asked again either.
                if _is_model_loop(exc):
                    unreachable = False
                    break

                unreachable = True
                if attempt < max_retries:
                    time.sleep(self._backoff_seconds(attempt))
                continue

            unreachable = False

            usage = getattr(response, "usage", None)
            call["promptTokens"] = getattr(usage, "prompt_tokens", None)
            call["completionTokens"] = getattr(usage, "completion_tokens", None)

            if attempt == 0:
                _warn_if_cut(model, len(system_prompt) + len(user_prompt), response)

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
            groq_note = f" ({call['fallback']})" if call.get("fallback") else ""
            raise LLMUnavailableError(
                f"{model} unreachable after {max_retries + 1} attempt(s){groq_note}"
                if ends_at is None or time.monotonic() < ends_at
                else f"{model} did not answer within {timeout:.0f} s{groq_note}"
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

    @staticmethod
    def _rate_limit_wait(exc: RateLimitError, ends_at: float | None) -> float | None:
        """
        Seconds a 429 asks to wait (`retry-after`), or None to fail as
        before: no header, a wait past RATE_LIMIT_MAX_WAIT_SECONDS (a
        daily cap), or one past the call's own deadline.
        """

        try:
            wait = float(exc.response.headers.get("retry-after", ""))
        except (AttributeError, ValueError):
            return None

        if wait < 0 or wait > RATE_LIMIT_MAX_WAIT_SECONDS:
            return None

        if ends_at is not None and time.monotonic() + wait >= ends_at - 1.0:
            return None

        return wait


def _reasoning_effort(model: str) -> dict:
    """The extra body field that sets `model`'s reasoning (LLM_REASONING_EFFORT), or nothing."""

    effort = settings.LLM_REASONING_EFFORT.get(model)

    return {"extra_body": {"reasoning_effort": effort}} if effort else {}


def _host(url: str) -> str:

    return (urlparse(url).hostname or "").lower()
