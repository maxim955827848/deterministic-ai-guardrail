"""End-to-end wrapper tests — the three layers behind one call, with retry+fallback."""
from guardrail import AgentAction, AgentStatus, GuardedAgent, ScriptedLLM

_GOOD = (
    '{"action": "advance", "status": "active", "summary": "go", '
    '"confidence": 0.9, "priority": 2, "resource_delta": {"energy": -5}}'
)
_GOOD_FENCED = f"```json\n{_GOOD}\n```"
_MALFORMED = "{not json"
_BAD_ENUM = (
    '{"action": "explode", "status": "active", "summary": "x", '
    '"confidence": 0.5, "priority": 1}'
)


def _state():
    return {"energy": 50.0, "reputation": 40.0, "credits": 1000.0, "throughput": 100.0}


def test_happy_path_first_attempt():
    agent = GuardedAgent(ScriptedLLM([_GOOD]))
    result = agent.step(_state(), "act")
    assert not result.used_fallback
    assert result.attempts == 1
    assert result.directive.action is AgentAction.ADVANCE
    assert result.state["energy"] == 45.0


def test_fenced_output_is_recovered():
    agent = GuardedAgent(ScriptedLLM([_GOOD_FENCED]))
    result = agent.step(_state(), "act")
    assert not result.used_fallback


def test_retry_recovers_after_malformed_first_response():
    agent = GuardedAgent(ScriptedLLM([_MALFORMED, _GOOD]))
    result = agent.step(_state(), "act")
    assert not result.used_fallback
    assert result.attempts == 2
    assert result.directive.action is AgentAction.ADVANCE


def test_fallback_after_all_attempts_fail():
    agent = GuardedAgent(ScriptedLLM([_MALFORMED, _BAD_ENUM]))
    result = agent.step(_state(), "act")
    assert result.used_fallback
    assert result.directive.action is AgentAction.HOLD
    assert result.directive.status is AgentStatus.BLOCKED
    # State is untouched on fallback.
    assert result.state == _state()


def test_state_never_mutated_by_step():
    before = _state()
    GuardedAgent(ScriptedLLM([_GOOD])).step(before, "act")
    assert before["energy"] == 50.0


def test_absurd_delta_is_clamped_end_to_end():
    absurd = (
        '{"action": "advance", "status": "active", "summary": "boom", '
        '"confidence": 0.5, "priority": 1, "resource_delta": {"credits": 999999999}}'
    )
    agent = GuardedAgent(ScriptedLLM([absurd]))
    result = agent.step(_state(), "act")
    assert not result.used_fallback
    # credits 1000 -> capped at 3x = 3000 by growth cap, well under the 9.99M ceiling.
    assert result.state["credits"] == 3000.0
    assert not result.apply_result.clean
