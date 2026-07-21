"""Layer 1 — JSON boundary tests."""
import pytest

from guardrail import safe_parse_json


def test_plain_object_parses():
    assert safe_parse_json('{"a": 1}') == {"a": 1}


def test_code_fence_wrapped_is_recovered():
    parsed = safe_parse_json('```json\n{"action": "advance"}\n```')
    assert parsed["action"] == "advance"


def test_prose_wrapped_object_is_recovered():
    raw = 'Sure! Here is the result: {"action": "hold", "priority": 2} Hope that helps!'
    assert safe_parse_json(raw) == {"action": "hold", "priority": 2}


def test_malformed_json_raises():
    with pytest.raises(ValueError):
        safe_parse_json("{not valid json at all")


def test_top_level_array_raises():
    # Valid JSON, but structurally wrong — we require an object.
    with pytest.raises(ValueError):
        safe_parse_json("[1, 2, 3]")


def test_top_level_string_raises():
    with pytest.raises(ValueError):
        safe_parse_json('"just a string"')


def test_prototype_pollution_key_rejected():
    with pytest.raises(ValueError):
        safe_parse_json('{"__proto__": {"polluted": true}}')


def test_nested_dangerous_key_rejected():
    with pytest.raises(ValueError):
        safe_parse_json('{"resource_delta": {"constructor": 1}}')
