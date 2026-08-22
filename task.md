# Task: Backend Activity Logging Infrastructure

## Objective

Store meaningful backend user activity in MongoDB for analytics, auditing,
debugging, and future AI training.

## Scope Completed

- Added `activity_logs` MongoDB collection access.
- Added indexes for `timestamp`, `user_id`, `action`, and `category`.
- Added `rag-backend/app/activity_logger.py`.
- Integrated logging into authentication endpoints only:
  - Register
  - Send OTP
  - Verify OTP
  - Login
  - Refresh Token
  - Logout
- Added graceful logging failure handling.

## Out Of Scope

- No admin dashboard.
- No frontend changes.
- No authentication flow changes.
- No API contract changes.

## Verification

Backend syntax check:

```bash
cd rag-backend
./.venv/bin/python -m py_compile app/activity_logger.py app/database.py app/api/auth.py
```

Activity insertion was verified with a mocked Mongo collection by calling
`log_activity(...)` and confirming one document was inserted with the expected
action, category, metadata, request fields, success state, and duration.
