"""
Layer 3 — the deterministic state-application layer.

The schema (Layer 2) proves a directive is *well-formed*. It cannot prove the
directive is *reasonable*. A value can be perfectly typed and in its declared
range yet still be economically absurd for the current state — a delta that
triples a resource in a single step, or drives a bounded quantity past its hard
ceiling.

`apply_directive` is where the application, not the model, has the final say. It:

  * skips deltas for keys the world does not own (no key injection),
  * skips non-numeric deltas rather than crashing,
  * caps per-step growth of any resource to a fixed multiple of its current
    value (the model cannot 100x a number in one move),
  * clamps every resulting value into a hard [min, max] range, and
  * records every intervention in a structured ``errors`` collector so the
    caller has an audit trail of exactly what the model tried and what the
    system did instead.

Every rule here is pure and deterministic: same state + same directive always
produces the same result and the same error log. There is no model in this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Hard [min, max] bounds for each world-state resource. A resulting value outside
# its band is clamped to the nearest edge. Keys absent from this map are treated
# as unknown and their deltas are skipped entirely.
CLAMP_RANGES: dict[str, tuple[float, float]] = {
    "energy": (0.0, 100.0),
    "reputation": (0.0, 100.0),
    "credits": (0.0, 9_999_999.0),
    "throughput": (0.0, 100_000.0),
}

# The most a single directive may multiply a positive resource by in one step.
# Blocks "went from 10 to 10,000,000" hallucinations even when the target is in
# a wide clamp band.
MAX_GROWTH_FACTOR = 3.0


@dataclass
class Intervention:
    """One deterministic correction the guard applied to a proposed value."""

    kind: str
    key: str
    proposed: Any = None
    applied: Any = None


@dataclass
class ApplyResult:
    """The outcome of applying a directive's ``resource_delta`` to a state."""

    state: dict[str, float]
    interventions: list[Intervention] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """True when the model's deltas were applied without any correction."""
        return not self.interventions


def apply_directive(
    state: dict[str, float],
    resource_delta: dict[str, Any],
) -> ApplyResult:
    """Apply ``resource_delta`` to a copy of ``state`` under deterministic rules.

    The input ``state`` is never mutated. Returns an :class:`ApplyResult` holding
    the new state and the list of interventions that were required.
    """
    new_state = dict(state)
    interventions: list[Intervention] = []

    for key, raw_delta in resource_delta.items():
        # 1. Key ownership — the model cannot invent new state keys.
        if key not in new_state:
            interventions.append(Intervention("unknown_key_skipped", key, proposed=raw_delta))
            continue

        # 2. Type safety — a non-numeric delta is dropped, never coerced blindly.
        try:
            delta = float(raw_delta)
        except (TypeError, ValueError):
            interventions.append(Intervention("non_numeric_skipped", key, proposed=raw_delta))
            continue

        current = new_state[key]
        proposed = current + delta

        # 3. Growth cap — bound how far a single step may move a positive value.
        if current > 0 and proposed > current * MAX_GROWTH_FACTOR:
            capped = current * MAX_GROWTH_FACTOR
            interventions.append(
                Intervention("growth_capped", key, proposed=proposed, applied=capped)
            )
            proposed = capped

        # 4. Hard range clamp.
        if key in CLAMP_RANGES:
            lo, hi = CLAMP_RANGES[key]
            clamped = max(lo, min(hi, proposed))
            if clamped != proposed:
                interventions.append(
                    Intervention("range_clamped", key, proposed=proposed, applied=clamped)
                )
            proposed = clamped

        new_state[key] = proposed

    return ApplyResult(state=new_state, interventions=interventions)
