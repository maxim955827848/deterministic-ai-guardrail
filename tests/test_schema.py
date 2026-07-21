"""Layer 2 — strict schema tests."""
import pytest
from pydantic import ValidationError

from guardrail import AgentAction, AgentDirective, AgentStatus


def _valid_payload(**overrides):
    payload = {
        "action": "advance",
        "status": "active",
        "summary": "moving forward",
        "confidence": 0.8,
        "priority": 3,
    }
    payload.update(overrides)
    return payload


def test_valid_payload_parses():
    d = AgentDirective.model_validate(_valid_payload())
    assert d.action is AgentAction.ADVANCE
    assert d.status is AgentStatus.ACTIVE
    assert d.resource_delta == {}


def test_missing_required_field_rejected():
    payload = _valid_payload()
    del payload["confidence"]
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(payload)


def test_invalid_enum_value_rejected():
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(_valid_payload(action="self_destruct"))


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(_valid_payload(confidence=1.5))


def test_priority_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(_valid_payload(priority=99))


def test_extra_key_forbidden():
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(_valid_payload(backdoor=True))


def test_empty_summary_rejected():
    with pytest.raises(ValidationError):
        AgentDirective.model_validate(_valid_payload(summary=""))


def test_resource_delta_accepted():
    d = AgentDirective.model_validate(_valid_payload(resource_delta={"energy": -10}))
    assert d.resource_delta == {"energy": -10.0}
