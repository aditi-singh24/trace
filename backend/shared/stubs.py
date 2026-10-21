"""Stand-ins so Module 2/3 can be developed before Modules 4/5 are merged.

Real implementations: module4_auth (check_permission, can_see_arm) and
module5_engine (randomize, record_audit_event).
"""
from __future__ import annotations


def check_permission(user, action: str) -> bool:
    return True


def can_see_arm(user) -> bool:
    return False


def randomize(participant_id: str, actor_id: str, db=None) -> dict:
    return {
        "message": "Participant randomized successfully",
        "participant_id": participant_id,
        "randomization_number": "RAND-9999",
        "arm": "A",
    }


def record_audit_event(event_type: str, actor_id: str, payload: dict, db=None) -> None:
    return None
