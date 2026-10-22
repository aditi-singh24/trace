"""Status names and placeholder rules used by Modules 2 and 3.

Kept local to Disha's modules so the shared contract (shared/constants.py) is not
changed. Roles, arms, trial weeks and hba1c_category come from shared.constants.
"""
from shared.constants import (  # noqa: F401
    ARMS, COORDINATOR, HBA1C_CUTOFF, PATIENT, SUPERVISOR, TRIAL_WEEKS, VISIT_WEEKS,
    hba1c_category,
)

# Eligibility status
PENDING_REVIEW = "PENDING_REVIEW"
ELIGIBLE = "ELIGIBLE"
SCREEN_FAILURE = "SCREEN_FAILURE"

# Trial status (RANDOMIZED is not stored; ACTIVE is derived)
SCREENING = "SCREENING"
ENROLLED = "ENROLLED"
COMPLETED = "COMPLETED"        # also used as a visit status
WITHDRAWN = "WITHDRAWN"        # also used as a consent status

# Consent status
NOT_OBTAINED = "NOT_OBTAINED"
OBTAINED = "OBTAINED"

# Visit status
SCHEDULED = "SCHEDULED"
MISSED = "MISSED"
RESCHEDULED = "RESCHEDULED"

# Adverse event status
SUBMITTED = "SUBMITTED"
UNDER_REVIEW = "UNDER_REVIEW"
CLOSED = "CLOSED"

# Alerts
OVERDUE_VISIT = "OVERDUE_VISIT"
MISSING_LAB_RESULT = "MISSING_LAB_RESULT"
INCOMPLETE_CONSENT = "INCOMPLETE_CONSENT"
PENDING_AE_REVIEW = "PENDING_AE_REVIEW"
INCOMPLETE_FORM = "INCOMPLETE_FORM"
ALERT_OPEN = "OPEN"
ALERT_RESOLVED = "RESOLVED"

# [OPEN] decision 4: placeholders until the Biotech member confirms the protocol rules.
ELIGIBILITY_AGE_MIN = 18
ELIGIBILITY_AGE_MAX = 65
ELIGIBILITY_HBA1C_MIN = 7.0
ELIGIBILITY_HBA1C_MAX = 10.5

# Baseline is complete once week-0 data has all of these.
BASELINE_REQUIRED = ("hba1c", "fasting_glucose", "weight_kg")

# Abnormal-reading flags support review and never diagnose. [PROPOSED]
ABNORMAL_RANGES = {
    "systolic": (90, 160), "diastolic": (60, 100), "heart_rate": (50, 100),
    "resp_rate": (12, 20), "temperature_c": (35.5, 38.0), "spo2": (92, 100),
    "fasting_glucose": (70, 250),
}
