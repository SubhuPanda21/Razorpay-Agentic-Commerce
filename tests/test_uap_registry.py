from src.protocols import uap_registry


def test_unregistered_agent_rejected(db_session):
    ok, reason = uap_registry.is_trusted(db_session, "unknown-agent", 1, 500)
    assert ok is False
    assert reason == "agent_not_registered_in_trust_registry"


def test_registered_agent_within_ceiling_trusted(db_session):
    uap_registry.register(db_session, "agent-a", 1, spending_ceiling=5000)
    ok, reason = uap_registry.is_trusted(db_session, "agent-a", 1, 3000)
    assert ok is True
    assert reason is None


def test_registered_agent_over_ceiling_rejected(db_session):
    uap_registry.register(db_session, "agent-a", 1, spending_ceiling=1000)
    ok, reason = uap_registry.is_trusted(db_session, "agent-a", 1, 5000)
    assert ok is False
    assert "ceiling" in reason


def test_re_register_updates_ceiling(db_session):
    uap_registry.register(db_session, "agent-a", 1, spending_ceiling=1000)
    uap_registry.register(db_session, "agent-a", 1, spending_ceiling=9000)
    ok, _ = uap_registry.is_trusted(db_session, "agent-a", 1, 5000)
    assert ok is True
