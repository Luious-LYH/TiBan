"""Pure durable-job state rules owned by the Factory application slice."""

from __future__ import annotations

from collections.abc import Mapping


TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
ACTIVE_JOB_STATUSES = frozenset({"queued", "running", "retrying"})
_ALLOWED: Mapping[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled"}),
    "retrying": frozenset({"queued", "running", "cancelled", "failed"}),
    "running": frozenset({"succeeded", "failed", "cancelled", "retrying"}),
    "failed": frozenset({"queued", "retrying"}),
    "succeeded": frozenset(),
    "cancelled": frozenset(),
}


class JobTransitionError(ValueError):
    pass


def ensure_transition(current: str, target: str) -> None:
    if current == target:
        return
    if target not in _ALLOWED.get(current, frozenset()):
        raise JobTransitionError(f"invalid factory job transition: {current} -> {target}")
