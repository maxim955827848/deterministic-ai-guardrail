"""
Layer 2 — the strict schema boundary.

A Large Language Model is an *untrusted narrator*. It is superb at proposing
structure and terrible at guaranteeing it: fields go missing, enums get
invented, numbers arrive out of range, and extra keys sneak in. Before a single
value from a model is allowed to touch application state, it must pass through a
schema that rejects anything it cannot vouch for.

`AgentDirective` is a deliberately generic example — an agent proposing its next
action and a set of numeric adjustments to a shared world state. It carries no
domain business logic; swap it for your own model and the guardrail machinery in
`parser.py`, `clamps.py`, and `wrapper.py` is unchanged.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AgentAction(str, Enum):
    """The closed set of moves an agent may propose.

    Using an Enum (rather than a bare ``str``) means a hallucinated action such
    as ``"self_destruct"`` is rejected at the schema boundary instead of being
    dispatched downstream.
    """

    ADVANCE = "advance"
    HOLD = "hold"
    RETREAT = "retreat"
    TERMINATE = "terminate"


class AgentStatus(str, Enum):
    """Lifecycle state the agent reports for itself."""

    ACTIVE = "active"
    IDLE = "idle"
    BLOCKED = "blocked"
    DONE = "done"


class AgentDirective(BaseModel):
    """A single validated instruction emitted by an LLM.

    ``extra="forbid"`` is the load-bearing line: a model that appends an
    unexpected key (a common failure mode, and a prompt-injection vector) is
    rejected outright rather than silently carrying an un-audited field into the
    system.
    """

    model_config = ConfigDict(extra="forbid")

    # ── Required fields ────────────────────────────────────────────────────
    # No defaults: if the model omits these, validation fails and the wrapper
    # retries. A "quiet" turn must still *say* it is quiet.
    action: AgentAction
    status: AgentStatus
    summary: str = Field(min_length=1, max_length=2000)

    # ── Constrained numerics ───────────────────────────────────────────────
    # Pydantic enforces the declared range at the boundary. Values that arrive
    # outside it are a hard validation error here; values that are *in range but
    # economically implausible* are handled separately by the clamp layer.
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=1, le=5)

    # ── Optional structured payload ────────────────────────────────────────
    # Proposed additive changes to numeric world-state keys, e.g.
    # ``{"energy": -10, "reputation": 5}``. Defaults to empty so a legitimately
    # no-op directive need not enumerate anything.
    resource_delta: dict[str, float] = Field(default_factory=dict)
