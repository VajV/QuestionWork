---
name: backend-endpoint
description: 'Create or modify FastAPI endpoints in QuestionWork. Use for route handlers, service-layer work, router registration, request validation, transactions, rate limiting, and backend tests.'
argument-hint: 'Describe the endpoint or backend change to implement'
---

# Backend Endpoint Workflow

## When to Use
- Adding a new backend endpoint
- Modifying request or response models
- Moving logic out of route handlers into services
- Fixing missing router registration, rate limiting, or transaction handling

## Procedure
1. Identify the endpoint module, service module, models, and router registration file.
2. Keep HTTP handlers thin and move business logic into a service function.
3. For mutations, wrap multi-step writes in a transaction and use row locking when required.
4. Add `check_rate_limit()` for POST, PATCH, and DELETE handlers.
5. Update or add response/request models as needed.
6. Register routers in `backend/app/api/v1/api.py`.
7. Add or update backend tests for the main success and failure paths.

## Done Criteria
- Endpoint is registered and reachable through `/api/v1`
- No SQL lives in the route handler
- Transaction and rate-limit rules are satisfied
- Tests cover the changed behavior
