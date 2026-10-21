"""Shared contract for TRACE. Change only by agreement between both IT members."""

# Roles
PATIENT = "PATIENT"
COORDINATOR = "COORDINATOR"
SUPERVISOR = "SUPERVISOR"
ROLES = [PATIENT, COORDINATOR, SUPERVISOR]

# Statuses
ELIGIBILITY_STATUSES = ["PENDING_REVIEW", "ELIGIBLE", "SCREEN_FAILURE"]
TRIAL_STATUSES = ["SCREENING", "ENROLLED", "ACTIVE", "COMPLETED", "WITHDRAWN"]
CONSENT_STATUSES = ["NOT_OBTAINED", "OBTAINED", "WITHDRAWN"]
VISIT_STATUSES = ["SCHEDULED", "COMPLETED", "MISSED", "RESCHEDULED"]
AE_STATUSES = ["SUBMITTED", "UNDER_REVIEW", "CLOSED"]
AE_SEVERITIES = ["MILD", "MODERATE", "SEVERE"]
AE_RELATIONSHIPS = ["NOT_RELATED", "POSSIBLY_RELATED", "RELATED"]

# Trial constants
TRIAL_WEEKS = 16
VISIT_WEEKS = [0, 4, 8, 12, 16]
ARMS = ["A", "B"]

# Stratification
SITES = ["SITE-01", "SITE-02"]  # [OPEN] default
HBA1C_CATEGORIES = ["LOW", "HIGH"]  # LOW < 8.5, HIGH >= 8.5
HBA1C_CUTOFF = 8.5
THERAPY_VALUES = ["STABLE", "NONE"]  # [OPEN] default: include
USE_THERAPY_FACTOR = True  # set False if the team drops the therapy factor
BLOCK_SIZE = 4  # 2 of A and 2 of B per block

# Hash chain
GENESIS_HASH = "0" * 64
CHAINED_EVENT_TYPES = {"RANDOMIZED"}  # [OPEN] default: RANDOMIZED only

# Identifier formats
PARTICIPANT_ID_PREFIX = "SUB-"
USER_ID_PREFIX = "U-"
RAND_NUMBER_PREFIX = "RAND-"


def hba1c_category(value: float) -> str:
    """Return LOW (<8.5) or HIGH (>=8.5)."""
    return "HIGH" if value >= HBA1C_CUTOFF else "LOW"
