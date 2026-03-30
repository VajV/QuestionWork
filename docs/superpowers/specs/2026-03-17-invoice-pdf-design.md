# Invoice PDF Design

Date: 2026-03-17
Feature: Wallet receipt and statement export
Source: [docs/ideas/10-invoice-pdf.md](docs/ideas/10-invoice-pdf.md)

## Goal

Allow authenticated users to generate accounting-friendly wallet documents on demand: a receipt PDF for a single transaction and a statement export for a date range in PDF or CSV.

## Current Reality

- Wallet balances and transaction history already exist in [backend/app/api/v1/endpoints/wallet.py](backend/app/api/v1/endpoints/wallet.py) and [backend/app/services/wallet_service.py](backend/app/services/wallet_service.py).
- The wallet history payload already exposes transaction id, amount, currency, type, status, created_at, and quest_id.
- The wallet UI already renders transaction history in [frontend/src/components/rpg/WalletPanel.tsx](frontend/src/components/rpg/WalletPanel.tsx).
- There is no document export service, no download endpoints, and no frontend actions for receipt or statement exports.

## Chosen Approach

Implement on-demand document generation with ReportLab for PDF and the Python csv module for CSV.

### Why this approach

- Avoids Windows-hostile system dependencies like wkhtmltopdf or browser-based renderers.
- Keeps document generation inside backend Python code, which is easier to test in this repository.
- Matches the requested runtime model: generate on request and stream immediately, with no persistent file storage.
- Keeps MVP scope aligned with the existing wallet ledger instead of introducing a separate invoicing subsystem.

## Output Model

### Receipt PDF

Generated from a single wallet transaction identified by transaction id.

Fields included in MVP:

- document title
- receipt id
- transaction id
- transaction date/time
- operation type
- transaction status
- amount
- currency
- counterparty or fallback placeholder
- platform fee or fallback placeholder
- optional quest reference when present
- account owner username

### Statement PDF / CSV

Generated from a user-selected inclusive date range.

Fields included per row:

- transaction id
- created_at
- type
- status
- amount
- currency
- quest_id

Summary block included in PDF:

- statement period
- account owner
- total transaction count
- total inflow
- total outflow

## Data Rules

- Access is limited to the authenticated user’s own wallet transactions.
- Receipt lookup must return 404 when the transaction does not belong to the current user.
- Statement date filters are inclusive and validated so `from <= to`.
- CSV uses UTF-8 and deterministic column ordering.
- Amounts continue to use Decimal-backed values from the existing wallet service and are serialized as user-facing strings/numbers only at the response boundary.

## Backend Design

### New service

Create [backend/app/services/invoice_service.py](backend/app/services/invoice_service.py) with:

- `get_wallet_receipt_data(conn, user_id, transaction_id)`
- `get_wallet_statement_data(conn, user_id, date_from, date_to)`
- `generate_receipt_pdf(receipt_data)`
- `generate_statement_pdf(statement_data)`
- `generate_statement_csv(statement_data)`

The service is responsible for:

- querying and validating ownership of wallet transactions
- deriving fallback display values for missing counterparty or platform fee data
- building byte payloads for PDF/CSV generation

### API surface

Extend [backend/app/api/v1/endpoints/wallet.py](backend/app/api/v1/endpoints/wallet.py) with:

- `GET /wallet/transactions/{transaction_id}/receipt`
- `GET /wallet/statements?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /wallet/statements?from=YYYY-MM-DD&to=YYYY-MM-DD&format=csv`

Endpoint behavior:

- require auth
- reuse existing DB dependency pattern
- return `StreamingResponse` or `Response` with correct `Content-Type`
- set `Content-Disposition` for download-friendly filenames
- convert invalid input to 400 and missing ownership/resource to 404

### Dependency change

Add `reportlab` to [backend/requirements.txt](backend/requirements.txt).

## Frontend Design

### API client

Extend [frontend/src/lib/api.ts](frontend/src/lib/api.ts) with download helpers that:

- call the new wallet endpoints with auth enabled
- return `Blob` payloads
- preserve current `fetchApi` conventions for authenticated requests

### Types

Extend [frontend/src/types/index.ts](frontend/src/types/index.ts) only if needed for statement request helpers or stronger wallet transaction typing.

### Wallet panel

Extend [frontend/src/components/rpg/WalletPanel.tsx](frontend/src/components/rpg/WalletPanel.tsx) with:

- a receipt download action on each transaction row
- a compact statement export form with `from`, `to`, and format selection
- loading/error states for document downloads independent from balance loading

## Non-Goals

- No persistent document storage or document history table.
- No HTML templating engine for PDF generation in MVP.
- No tax-form generation such as 1099, acts, or jurisdiction-specific filings.
- No admin-side export UI in this increment.

## Verification

- Backend service tests for receipt lookup, statement filtering, and generated non-empty PDF/CSV output.
- Wallet endpoint tests for auth, success responses, invalid date validation, and ownership failures.
- Frontend TypeScript validation after client/UI changes.