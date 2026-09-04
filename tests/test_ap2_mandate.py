import time
from src.protocols import ap2_mandate


def test_valid_mandate_verifies():
    token = ap2_mandate.issue_mandate("agent-1", 1, 5000, ttl_seconds=60)
    ok, reason = ap2_mandate.verify_mandate(token, merchant_id=1, amount=3000, buyer_agent_id="agent-1")
    assert ok is True
    assert reason is None


def test_amount_over_ceiling_rejected():
    token = ap2_mandate.issue_mandate("agent-1", 1, 1000, ttl_seconds=60)
    ok, reason = ap2_mandate.verify_mandate(token, merchant_id=1, amount=5000, buyer_agent_id="agent-1")
    assert ok is False
    assert "ceiling" in reason


def test_wrong_agent_rejected():
    token = ap2_mandate.issue_mandate("agent-1", 1, 5000, ttl_seconds=60)
    ok, reason = ap2_mandate.verify_mandate(token, merchant_id=1, amount=100, buyer_agent_id="agent-999")
    assert ok is False
    assert reason == "mandate_agent_mismatch"


def test_expired_mandate_rejected():
    token = ap2_mandate.issue_mandate("agent-1", 1, 5000, ttl_seconds=0)
    time.sleep(1.1)
    ok, reason = ap2_mandate.verify_mandate(token, merchant_id=1, amount=100, buyer_agent_id="agent-1")
    assert ok is False
    assert reason == "mandate_expired"


def test_tampered_token_rejected():
    token = ap2_mandate.issue_mandate("agent-1", 1, 5000, ttl_seconds=60)
    tampered = token[:-4] + "abcd"
    ok, reason = ap2_mandate.verify_mandate(tampered, merchant_id=1, amount=100, buyer_agent_id="agent-1")
    assert ok is False
    assert reason == "invalid_mandate_signature"
