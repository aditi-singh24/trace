"""Module 4: Auth & Access (owner: Aditi).

Public handshake for other modules:
    check_permission(user, action) -> bool
    can_see_arm(user) -> bool
    get_current_user  (FastAPI dependency)
"""
from module4_auth.dependencies import get_current_user, require_permission
from module4_auth.permissions import can_access_participant, can_see_arm, check_permission

__all__ = [
    "check_permission",
    "can_see_arm",
    "can_access_participant",
    "get_current_user",
    "require_permission",
]
