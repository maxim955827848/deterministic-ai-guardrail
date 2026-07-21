"""
The model seam.

The guardrail is deliberately provider-agnostic: it depends only on the tiny
:class:`LLMClient` protocol below — "give me a prompt, hand me back raw text."
Drop in an OpenAI / Anthropic / OpenRouter client that satisfies this shape and
nothing else in the package changes.

For the PoC (and for the test-suite) we ship :class:`ScriptedLLM`, a
deterministic fake that replays a fixed list of responses. That lets us exercise
every guardrail branch — malformed JSON, schema violations, absurd numbers, and
the happy path — without a network call or an API key.
"""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """The only thing the guardrail needs from a model provider."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's raw text output for the given prompts."""
        ...


class ScriptedLLM:
    """A deterministic ``LLMClient`` that replays canned responses in order.

    Each call to :meth:`complete` returns the next scripted response. Once the
    script is exhausted the last response repeats, so a wrapper that retries more
    times than the script is long still terminates predictably.
    """

    def __init__(self, responses: list[str]) -> None:
        if not responses:
            raise ValueError("ScriptedLLM needs at least one response")
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]
