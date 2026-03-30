---
name: Create Backend Endpoint
description: "Create or modify a QuestionWork FastAPI endpoint with service-layer logic, rate limiting, router registration, and tests."
argument-hint: "Describe the endpoint to add or change"
agent: "agent"
---
Implement the requested backend endpoint for QuestionWork.

Requirements:
- Follow the endpoint -> service -> query layering
- Add `check_rate_limit()` for mutating handlers
- Register the router if needed
- Update or add tests for the changed behavior
- Keep request and response models aligned with the frontend contract when relevant
