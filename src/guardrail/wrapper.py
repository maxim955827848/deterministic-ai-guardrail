"""
The orchestrator — where the three layers meet a real (non-deterministic) model.

`GuardedAgent.step` is the single entry point an application calls instead of
hitting the model directly. It guarantees one of exactly two outcomes:

  1. a *validated* :class:`AgentDirective` and a deterministically-guarded new
     state, or
  2. an explicit, safe fallback directive with the state left untouched.

There is no third outcome. The application never receives a half-parsed dict, a
hallucinated enum, or an out-of-range number. Non-determinism is quarantined to
the model call; everything downstream of ``step`` is deterministic.

The retry policy mirrors the production system this PoC was extracted from:

  * Attempt 1: call the model, parse, validate.
  * On failure: re-prompt once with an explicit "return only valid JSON"
    instruction (models very often self-correct on the second pass).
  * On a second failure: stop calling the model and return a deterministic
    fallback directive (``HOLD`` / ``BLOCKED``) so the caller has a safe,
    typed value to act on rather than an exception to handle.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from .clamps import ApplyResult, apply_directive
from .llm import LLMClient
from .parser import safe_parse_json
from .schema import AgentAction, AgentDirective, AgentStatus

RETRY_INSTRUCTION = (
    "Your previous reply could not be parsed. Reply with ONLY a single JSON "
    "object matching the required schema — no markdown fences, no prose, no "
    "explanation."
)

DEFAULT_SYSTEM_PROMPT = (
    "You are an agent controller. Respond with ONLY a JSON object describing "
    "the agent's next directive."
)


@dataclass
class StepResult:
    """The fully-guarded outcome of one agent step."""

    directive: AgentDirective
    apply_result: ApplyResult
    used_fallback: bool
    attempts: int

    @property
    def state(self) -> dict[str, float]:
        return self.apply_result.state


def _fallback_directive(reason: str) -> AgentDirective:
    """A safe, typed directive used when the model cannot be trusted this step."""
    return AgentDirective(
        action=AgentAction.HOLD,
        status=AgentStatus.BLOCKED,
        summary=f"Deterministic fallback: {reason}",
        confidence=0.0,
        priority=1,
        resource_delta={},
    )


class GuardedAgent:
    """Wraps an :class:`LLMClient` behind the parse → validate → apply pipeline."""

    def __init__(
        self,
        client: LLMClient,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._client = client
        self._system_prompt = system_prompt
        self._max_attempts = max_attempts

    def _try_once(self, user_prompt: str) -> AgentDirective:
        """One model round-trip through Layers 1 and 2. Raises on any failure."""
        raw = self._client.complete(self._system_prompt, user_prompt)
        parsed = safe_parse_json(raw)  # Layer 1
        return AgentDirective.model_validate(parsed)  # Layer 2

    def step(self, state: dict[str, float], user_prompt: str) -> StepResult:
        """Advance one step. Always returns a :class:`StepResult` — never raises
        on a bad model output.
        """
        last_error: str = "unknown"

        for attempt in range(1, self._max_attempts + 1):
            prompt = user_prompt
            if attempt > 1:
                prompt = f"{user_prompt}\n\n{RETRY_INSTRUCTION}"
            try:
                directive = self._try_once(prompt)
            except (ValueError, ValidationError) as exc:
                last_error = str(exc).splitlines()[0][:200]
                continue

            # Layer 3 — deterministic state application.
            apply_result = apply_directive(state, directive.resource_delta)
            return StepResult(
                directive=directive,
                apply_result=apply_result,
                used_fallback=False,
                attempts=attempt,
            )

        # Every attempt failed — return a safe fallback and leave state untouched.
        return StepResult(
            directive=_fallback_directive(last_error),
            apply_result=ApplyResult(state=dict(state)),
            used_fallback=True,
            attempts=self._max_attempts,
        )
