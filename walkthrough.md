# LETA Activity Logging Walkthrough

## Overview

The backend now records meaningful authentication activity in MongoDB using the
`activity_logs` collection. The logging layer is intentionally non-blocking for
request handling: if MongoDB logging fails, the API request continues and a
warning is written to application logs.

## Collection

Collection name: `activity_logs`

Example document shape:

```json
{
  "user_id": "...",
  "username": "...",
  "phone": "...",
  "email": "...",
  "timestamp": "ISODate(...)",
  "action": "login",
  "category": "authentication",
  "metadata": {},
  "ip_address": "...",
  "user_agent": "...",
  "request_id": "...",
  "success": true,
  "duration_ms": 120
}
```

## Helper

The shared helper lives in `rag-backend/app/activity_logger.py`.

`log_activity(...)` accepts:

- `user`
- `action`
- `category`
- `metadata`
- `request`
- `success`
- `duration`

It normalizes user fields, extracts IP/user-agent/request ID from the FastAPI
request, and inserts the activity document into MongoDB.

## Indexed Fields

The backend ensures indexes on:

- `timestamp`
- `user_id`
- `action`
- `category`

## Integrated Endpoints

Activity logging is integrated only in:

- Register
- Send OTP
- Verify OTP
- Login
- Refresh Token
- Logout

No frontend code, admin dashboard, API contracts, or authentication flow were
changed for this logging layer.

## Failure Handling

Logging failures are wrapped in `try/except` inside `log_activity(...)`.
Failures never crash the request and are reported only as warnings.
