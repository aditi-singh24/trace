"""Permission matrix and the blinding rule. Pure functions, no database access.

`user` is any object with: role, active, unblinded, participant_id.
Deny by default: unknown actions and inactive users are always refused.
"""
from __future__ import annotations

from shared.constants import COORDINATOR, PATIENT, SUPERVISOR

# Action names
VIEW_OWN_RECORD = "view_own_record"
VIEW_PARTICIPANTS = "view_participants"
ENROLL_CONSENT_SCREEN = "enroll_consent_screen"
RECORD_VISITS_MEASUREMENTS = "record_visits_measurements"
REPORT_ADVERSE_EVENT = "report_adverse_event"  # patients: own only (see can_access_participant)
REVIEW_ADVERSE_EVENTS = "review_adverse_events"
VIEW_ADVERSE_EVENTS = "view_adverse_events"  # supervisor is view-only
RANDOMIZE = "randomize"
OPERATIONAL_DASHBOARD = "operational_dashboard"
OVERSIGHT_DASHBOARD = "oversight_dashboard"
EXPORT_CSV = "export_csv"
VIEW_AUDIT = "view_audit"  # view audit log and verify chain
MANAGE_USERS = "manage_users"
SEE_ARM = "see_arm"  # delegated to can_see_arm

PERMISSION_MATRIX = {
    VIEW_OWN_RECORD: frozenset({PATIENT, COORDINATOR, SUPERVISOR}),
    VIEW_PARTICIPANTS: frozenset({COORDINATOR, SUPERVISOR}),
    ENROLL_CONSENT_SCREEN: frozenset({COORDINATOR}),
    RECORD_VISITS_MEASUREMENTS: frozenset({COORDINATOR}),
    REPORT_ADVERSE_EVENT: frozenset({PATIENT, COORDINATOR}),
    REVIEW_ADVERSE_EVENTS: frozenset({COORDINATOR}),
    VIEW_ADVERSE_EVENTS: frozenset({COORDINATOR, SUPERVISOR}),
    RANDOMIZE: frozenset({COORDINATOR}),
    OPERATIONAL_DASHBOARD: frozenset({COORDINATOR, SUPERVISOR}),
    OVERSIGHT_DASHBOARD: frozenset({SUPERVISOR}),
    EXPORT_CSV: frozenset({SUPERVISOR}),
    VIEW_AUDIT: frozenset({SUPERVISOR}),
    MANAGE_USERS: frozenset({SUPERVISOR}),
}

ALL_ACTIONS = list(PERMISSION_MATRIX) + [SEE_ARM]


def can_see_arm(user) -> bool:
    """The single place the blinding rule lives.

    Only an active SUPERVISOR with the unblinded flag may see the arm.
    Everyone else (patients, coordinators, blinded supervisors, no user) may not.
    """
    if user is None or not getattr(user, "active", False):
        return False
    return user.role == SUPERVISOR and bool(user.unblinded)


def check_permission(user, action: str) -> bool:
    if user is None or not getattr(user, "active", False):
        return False
    if action == SEE_ARM:
        return can_see_arm(user)
    return user.role in PERMISSION_MATRIX.get(action, frozenset())


def can_access_participant(user, participant_id: str) -> bool:
    """Patients may touch only their own participant record; staff may touch any."""
    if user is None or not getattr(user, "active", False):
        return False
    if user.role == PATIENT:
        return user.participant_id is not None and user.participant_id == participant_id
    return user.role in (COORDINATOR, SUPERVISOR)
