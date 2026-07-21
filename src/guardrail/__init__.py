"""
deterministic-ai-guardrail
==========================

A small, dependency-light demonstration of a three-layer boundary that turns a
non-deterministic LLM into a deterministic, auditable component:

    Layer 1  parser.py   Recover a JSON *object* from messy model text.
    Layer 2  schema.py   Validate it against a strict Pydantic v2 contract.
    Layer 3  clamps.py   Apply only sane, in-range changes to state.

`wrapper.py` composes the three behind a single ``GuardedAgent.step`` call that
retries, then falls back deterministically — the model never gets the last word.
"""
from __future__ import annotations

from .clamps import (
    CLAMP_RANGES,
    MAX_GROWTH_FACTOR,
    ApplyResult,
    Intervention,
    apply_directive,
)
from .llm import LLMClient, ScriptedLLM
from .parser import safe_parse_json
from .schema import AgentAction, AgentDirective, AgentStatus
from .wrapper import GuardedAgent, StepResult

__all__ = [
    "safe_parse_json",
    "AgentAction",
    "AgentStatus",
    "AgentDirective",
    "CLAMP_RANGES",
    "MAX_GROWTH_FACTOR",
    "Intervention",
    "ApplyResult",
    "apply_directive",
    "LLMClient",
    "ScriptedLLM",
    "GuardedAgent",
    "StepResult",
]

__version__ = "0.1.0"
