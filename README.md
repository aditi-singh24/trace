# TRACE: Randomization and audit

This repository includes a stratified 1:1 participant randomization engine and
hash-chained audit trail in the backend. The FastAPI routes are registered by
`backend/main.py` under `/api/v1`.

## Randomization

`POST /api/v1/randomization` accepts a participant ID:

```json
{
  "participant_id": "SUB-001"
}
```

The participant must exist in the `participants` table and meet all of these
conditions:

- `eligibility_status` is `ELIGIBLE`
- `consent_status` is `OBTAINED`
- `baseline_complete` is true
- `site_id` is present
- `hba1c_cat` is a configured category (`LOW` or `HIGH`)
- `therapy` is a configured value (`STABLE` or `NONE`) when the therapy
  stratification factor is enabled

Participants are assigned within a stratum formed from site, HbA1c category,
and, when enabled, therapy. Each shuffled allocation block has
`BLOCK_SIZE` slots with equal numbers of arms. The defaults are arms `A` and
`B`, a block size of four, and therapy stratification enabled; see
`backend/shared/constants.py` for the shared settings.

An assignment, allocation-slot update, and `RANDOMIZED` audit entry are saved
in the caller's transaction. The caller must commit or roll back that
transaction. When this function opens its own database session, it commits
before returning.

The API responds with a randomization number and assigned arm. The arm is
returned as `null` to callers who are not permitted to see it. The audit
payload deliberately excludes the arm.

Expected errors include:

| HTTP status | Meaning |
| --- | --- |
| 400 | A randomization prerequisite is not met |
| 404 | The participant does not exist |
| 409 | The participant has already been randomized |
| 422 | The request body is invalid |

## Audit endpoints

- `GET /api/v1/audit/entries` returns paginated audit entries.
- `GET /api/v1/audit/verify` checks the hash chain from its genesis entry and
  reports the first broken sequence, if any.

Both endpoints require audit-view permission. Audit entries are append-only;
the ORM prevents updates and deletes. The PostgreSQL trigger protection in
`backend/module5_engine/sql/append_only.sql` can also be applied after database
migrations to protect against raw SQL mutations.

## Configuration and development

Install the backend dependencies from the repository root:

```powershell
python -m pip install -r backend\requirements.txt
```

Set `DATABASE_URL` and `JWT_SECRET` in the environment (see
`backend\.env.example`), then start the API from the `backend` directory:

```powershell
uvicorn main:app --reload
```

`RANDOMIZATION_SEED` is optional. When set, it deterministically derives block
seeds from the master seed, stratum, and block number. When unset, each block
gets a cryptographically generated seed, which is stored with its allocation
slots so the block order can still be reproduced. A fixed seed is intended for
repeatable development or demonstrations, not operational randomization.

Run the randomization tests from the repository root:

```powershell
python -m pytest tests\test_randomization.py
```

The module reads participant data from a `participants` table supplied by
Module 2; it selects only the participant, site, HbA1c category, therapy,
eligibility, consent, and baseline-completion columns.
