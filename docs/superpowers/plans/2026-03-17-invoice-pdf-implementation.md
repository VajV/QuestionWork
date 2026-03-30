# Invoice PDF Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build authenticated on-demand wallet receipt PDF and statement PDF/CSV exports, and expose them in the wallet UI.

**Architecture:** Add a focused backend invoice service that reads wallet ledger data and renders PDFs with ReportLab plus CSV via the standard library. Wire new wallet download endpoints to that service, then add small frontend download actions in the existing wallet panel without creating a separate document module.

**Tech Stack:** FastAPI, asyncpg, ReportLab, Python csv module, React, TypeScript

---

## File Map

- Create: `backend/app/services/invoice_service.py`
- Create: `backend/tests/test_invoice_service.py`
- Modify: `backend/app/api/v1/endpoints/wallet.py`
- Modify: `backend/tests/test_wallet_endpoints.py`
- Modify: `backend/requirements.txt`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/rpg/WalletPanel.tsx`

## Chunk 1: Backend document service

### Task 1: Add backend dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] Add `reportlab` to backend Python dependencies.
- [ ] Verify the dependency name matches PyPI package naming already used in the repository.

Verification:

- [ ] Install backend requirements in the existing virtualenv if needed.

### Task 2: Write service tests first

**Files:**
- Create: `backend/tests/test_invoice_service.py`

- [ ] Add a receipt-data test that proves ownership filtering returns the expected transaction payload.
- [ ] Add a statement-data test that proves date-range filtering and summary totals are correct.
- [ ] Add PDF generation tests that assert returned bytes are non-empty and begin with `%PDF`.
- [ ] Add a CSV generation test that asserts the header row and at least one transaction row are present.

Verification:

- [ ] Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_invoice_service.py -q`
- [ ] Expected: failing tests before implementation.

### Task 3: Implement invoice service

**Files:**
- Create: `backend/app/services/invoice_service.py`

- [ ] Implement wallet receipt lookup for a single owned transaction.
- [ ] Implement statement lookup for owned transactions in an inclusive date range.
- [ ] Derive fallback values for counterparty and platform fee when ledger data does not provide them directly.
- [ ] Render receipt PDF bytes with a compact ReportLab layout.
- [ ] Render statement PDF bytes with a summary block plus transaction table.
- [ ] Render statement CSV bytes with deterministic UTF-8 column ordering.

Verification:

- [ ] Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_invoice_service.py -q`
- [ ] Expected: tests pass.

## Chunk 2: Wallet API integration

### Task 4: Add endpoint tests first

**Files:**
- Modify: `backend/tests/test_wallet_endpoints.py`

- [ ] Add auth-guard tests for receipt and statement endpoints.
- [ ] Add success tests for PDF receipt and PDF statement responses.
- [ ] Add a success test for CSV export response headers.
- [ ] Add invalid-range coverage for `from > to`.

Verification:

- [ ] Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_wallet_endpoints.py -q`
- [ ] Expected: new endpoint tests fail before endpoint implementation.

### Task 5: Implement wallet download endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/wallet.py`

- [ ] Add receipt download endpoint for `/wallet/transactions/{transaction_id}/receipt`.
- [ ] Add statement download endpoint for `/wallet/statements` with PDF default and CSV optional format.
- [ ] Validate query dates and convert service errors into appropriate HTTP status codes.
- [ ] Return attachment-friendly filenames and content types.

Verification:

- [ ] Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_invoice_service.py tests/test_wallet_endpoints.py -q`
- [ ] Expected: backend invoice and wallet tests pass.

## Chunk 3: Frontend wallet downloads

### Task 6: Add API helpers and types

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] Add download helpers for receipt and statement requests that return `Blob` objects.
- [ ] Add any narrow helper types needed for statement format or date-range requests.
- [ ] Keep auth handling aligned with existing wallet API calls.

Verification:

- [ ] Run: `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.json`
- [ ] Expected: temporary type failures until UI wiring is complete.

### Task 7: Extend wallet panel UI

**Files:**
- Modify: `frontend/src/components/rpg/WalletPanel.tsx`

- [ ] Add a per-transaction “Скачать чек” action.
- [ ] Add a small statement export form with `from`, `to`, and format controls.
- [ ] Add local loading/error state for downloads without regressing balance or history loading.
- [ ] Trigger browser downloads using the returned `Blob` payloads.

Verification:

- [ ] Run: `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.json`
- [ ] Expected: TypeScript passes.

## Chunk 4: Debugging and validation

### Task 8: Execute focused validation

**Files:**
- Test: `backend/tests/test_invoice_service.py`
- Test: `backend/tests/test_wallet_endpoints.py`

- [ ] Run backend invoice-related pytest slice.
- [ ] Run frontend TypeScript validation.
- [ ] Review CSV/PDF filenames and content-types for obvious contract issues.

Verification:

- [ ] Backend command: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_invoice_service.py tests/test_wallet_endpoints.py -q`
- [ ] Frontend command: `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.json`
- [ ] Expected: both succeed.

## Notes For Executing-Plans Review

- Preserve existing wallet endpoint behavior and response shapes for balance/history/withdraw.
- Keep the feature strictly user-scoped; do not introduce admin exports in this increment.
- If the current ledger cannot derive a real counterparty or fee, render a stable placeholder rather than inventing financial facts.