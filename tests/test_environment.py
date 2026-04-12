"""Tests for VoidEnvironment message inbox eviction and AgentOutput validation."""

import pytest
from environment.void import VoidEnvironment, Position
from agents.output import AgentOutput, AgentAction
from neural.models import CapabilityManifest, ActionCapability


# =============================================================================
# Helpers
# =============================================================================

def _make_manifest(available_actions: list[str]) -> CapabilityManifest:
    """Build a minimal CapabilityManifest with the given available actions."""
    actions = {
        name: ActionCapability(available=True, activation=1.0)
        for name in available_actions
    }
    return CapabilityManifest(agent_id="test-agent", tick=0, actions=actions)


def _env_with_entity(entity_id: str = "e1") -> VoidEnvironment:
    """Return a VoidEnvironment with one entity placed at the origin."""
    env = VoidEnvironment()
    env.set_position(entity_id, Position(0.0, 0.0))
    return env


def _inject_message(env: VoidEnvironment, entity_id: str, ticks_ago: int = 0) -> None:
    """Directly inject a message into an entity's inbox with the given ticks_ago."""
    inbox = env._message_inbox.setdefault(entity_id, [])
    inbox.append({"from_entity": "sender", "content": "hi", "ticks_ago": ticks_ago})


# =============================================================================
# VoidEnvironment — TTL eviction (10 ticks)
# =============================================================================

def test_message_survives_ten_calls_to_age_messages():
    """After 10 age_messages calls the first message is at ticks_ago==10 and still present."""
    env = _env_with_entity("e1")
    _inject_message(env, "e1", ticks_ago=0)

    for _ in range(10):
        env.age_messages()

    msgs = env.get_messages("e1")
    assert len(msgs) == 1
    assert msgs[0]["ticks_ago"] == 10


def test_message_evicted_after_eleven_calls():
    """After 11 age_messages calls the first message (ticks_ago==11) is evicted."""
    env = _env_with_entity("e1")
    _inject_message(env, "e1", ticks_ago=0)

    for _ in range(11):
        env.age_messages()

    msgs = env.get_messages("e1")
    assert len(msgs) == 0


def test_only_messages_within_ttl_remain_after_aging():
    """Messages 2-11 survive; the message from call 1 is evicted after 11 calls."""
    env = _env_with_entity("e1")

    # Inject one message per call (11 total)
    for i in range(11):
        _inject_message(env, "e1", ticks_ago=0)
        env.age_messages()

    # After 11 calls the oldest message has ticks_ago==11 and must be gone.
    msgs = env.get_messages("e1")
    assert all(m["ticks_ago"] <= 10 for m in msgs)
    # The 10 most recent messages (from calls 2-11) are still present.
    assert len(msgs) == 10


# =============================================================================
# VoidEnvironment — max-20 cap
# =============================================================================

def test_inbox_capped_at_20_after_age_messages():
    """Entity with 25 pre-existing messages is trimmed to 20 after one age call."""
    env = _env_with_entity("e1")
    # Inject 25 messages, all recent (ticks_ago=0), so none will be TTL-evicted
    for _ in range(25):
        _inject_message(env, "e1", ticks_ago=0)

    env.age_messages()

    msgs = env.get_messages("e1")
    assert len(msgs) == 20


def test_age_messages_on_empty_inbox_does_not_raise():
    """Calling age_messages on an entity with no messages must not raise."""
    env = _env_with_entity("e1")
    # entity has a position but no inbox entry yet
    env.age_messages()  # must not raise


# =============================================================================
# AgentOutput — is_valid_for_manifest
# =============================================================================

def test_agent_output_none_action_is_invalid():
    """AgentOutput with action=None must return False from is_valid_for_manifest."""
    manifest = _make_manifest(["locomotion", "signal_emitter"])
    output = AgentOutput(action=None, user_prompt_update=None)
    assert output.is_valid_for_manifest(manifest) is False


def test_agent_output_valid_action_is_valid():
    """AgentOutput with a valid action type returns True from is_valid_for_manifest."""
    manifest = _make_manifest(["locomotion", "signal_emitter"])
    output = AgentOutput(
        action=AgentAction(type="locomotion", parameters={"direction": "north"}),
        user_prompt_update=None,
    )
    assert output.is_valid_for_manifest(manifest) is True


def test_agent_output_unknown_action_type_is_invalid():
    """AgentOutput with an action type not in the manifest returns False."""
    manifest = _make_manifest(["locomotion"])
    output = AgentOutput(
        action=AgentAction(type="divide", parameters={}),
        user_prompt_update=None,
    )
    assert output.is_valid_for_manifest(manifest) is False
