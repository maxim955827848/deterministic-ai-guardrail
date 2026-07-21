"""Layer 3 — deterministic state-application tests."""
from guardrail import apply_directive


def _state():
    return {"energy": 50.0, "reputation": 40.0, "credits": 1000.0, "throughput": 100.0}


def test_clean_delta_applied_verbatim():
    result = apply_directive(_state(), {"energy": -10, "credits": 250})
    assert result.state["energy"] == 40.0
    assert result.state["credits"] == 1250.0
    assert result.clean


def test_input_state_is_not_mutated():
    before = _state()
    apply_directive(before, {"energy": -10})
    assert before["energy"] == 50.0


def test_unknown_key_is_skipped():
    result = apply_directive(_state(), {"mystery": 5})
    assert "mystery" not in result.state
    assert any(i.kind == "unknown_key_skipped" for i in result.interventions)


def test_non_numeric_delta_skipped():
    result = apply_directive(_state(), {"energy": "lots"})
    assert result.state["energy"] == 50.0
    assert any(i.kind == "non_numeric_skipped" for i in result.interventions)


def test_growth_capped_to_factor():
    # throughput 100 -> proposed +1,000,000; capped to 3x current = 300.
    result = apply_directive(_state(), {"throughput": 1_000_000})
    assert result.state["throughput"] == 300.0
    assert any(i.kind == "growth_capped" for i in result.interventions)


def test_range_clamped_to_ceiling():
    # energy 50 + 40 = 90 is within 3x (150) but energy is capped at 100... 90 is fine.
    # Push above the hard ceiling instead: 50 + 60 = 110 -> clamped to 100.
    result = apply_directive(_state(), {"energy": 60})
    assert result.state["energy"] == 100.0
    assert any(i.kind == "range_clamped" for i in result.interventions)


def test_range_clamped_to_floor():
    result = apply_directive(_state(), {"reputation": -100})
    assert result.state["reputation"] == 0.0
    assert any(i.kind == "range_clamped" for i in result.interventions)


def test_determinism_same_inputs_same_outputs():
    a = apply_directive(_state(), {"energy": 999, "credits": -5})
    b = apply_directive(_state(), {"energy": 999, "credits": -5})
    assert a.state == b.state
    assert [i.kind for i in a.interventions] == [i.kind for i in b.interventions]
