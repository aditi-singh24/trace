"""Module 5: Randomization Engine + Hash-Chained Audit (owner: Aditi).

Public handshake for other modules:
    randomize(participant_id, actor_id) -> result
    record_audit_event(event_type, actor_id, payload)

This package __init__ does not import the router, so Module 4 can import
module5_engine.audit without creating an import cycle.
"""
from module5_engine.audit import record_audit_event, verify_chain
from module5_engine.randomization import randomize

__all__ = ["randomize", "record_audit_event", "verify_chain"]
