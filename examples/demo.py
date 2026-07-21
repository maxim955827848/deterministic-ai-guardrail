"""
A runnable tour of the guardrail — no API key, no network.

We drive a ``GuardedAgent`` with a ``ScriptedLLM`` that deliberately misbehaves
in the ways real models do, and print what the guardrail did about it.

    python examples/demo.py
"""
from __future__ import annotations

from guardrail import GuardedAgent, ScriptedLLM

STATE = {"energy": 50.0, "reputation": 40.0, "credits": 1000.0, "throughput": 100.0}


def show(title: str, responses: list[str]) -> None:
    print(f"\n=== {title} ===")
    agent = GuardedAgent(ScriptedLLM(responses))
    result = agent.step(STATE, "Decide the agent's next move.")
    print(f"  used_fallback : {result.used_fallback}")
    print(f"  attempts      : {result.attempts}")
    print(f"  action/status : {result.directive.action.value} / {result.directive.status.value}")
    print(f"  new state     : {result.state}")
    if result.apply_result.interventions:
        for i in result.apply_result.interventions:
            print(f"  intervention  : {i.kind} on {i.key} "
                  f"(proposed={i.proposed}, applied={i.applied})")


def main() -> None:
    good = ('{"action": "advance", "status": "active", "summary": "on track", '
            '"confidence": 0.9, "priority": 2, "resource_delta": {"energy": -5}}')
    fenced = f"```json\n{good}\n```"
    absurd = ('{"action": "advance", "status": "active", "summary": "moon", '
              '"confidence": 0.5, "priority": 1, "resource_delta": {"credits": 999999999}}')
    bad_enum = ('{"action": "explode", "status": "active", "summary": "x", '
                '"confidence": 0.5, "priority": 1}')

    show("1. Clean happy path", [good])
    show("2. Model wrapped output in a markdown fence", [fenced])
    show("3. Model proposed an absurd number (clamped)", [absurd])
    show("4. Malformed then valid (retry recovers)", ["{not json", good])
    show("5. Two bad responses (deterministic fallback)", ["{not json", bad_enum])


if __name__ == "__main__":
    main()
