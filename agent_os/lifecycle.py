"""Agent lifecycle states and allowed transitions."""

from __future__ import annotations

from enum import Enum


class AgentLifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DRAINING = "DRAINING"
    DISABLED = "DISABLED"


# Valid directed transitions
ALLOWED_TRANSITIONS = {
    AgentLifecycleState.REGISTERED: {AgentLifecycleState.ACTIVE, AgentLifecycleState.DISABLED},
    AgentLifecycleState.ACTIVE: {AgentLifecycleState.PAUSED, AgentLifecycleState.DRAINING, AgentLifecycleState.DISABLED},
    AgentLifecycleState.PAUSED: {AgentLifecycleState.ACTIVE, AgentLifecycleState.DISABLED},
    AgentLifecycleState.DRAINING: {AgentLifecycleState.DISABLED, AgentLifecycleState.ACTIVE},
    AgentLifecycleState.DISABLED: {AgentLifecycleState.REGISTERED, AgentLifecycleState.ACTIVE},
}


def can_transition(current: AgentLifecycleState, target: AgentLifecycleState) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def can_accept_new_work(state: AgentLifecycleState) -> bool:
    return state == AgentLifecycleState.ACTIVE


def can_continue_work(state: AgentLifecycleState) -> bool:
    return state in (AgentLifecycleState.ACTIVE, AgentLifecycleState.DRAINING)
