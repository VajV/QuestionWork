---
name: quest-flow-regression
description: 'Protect the core QuestionWork business flow. Use when changing quest lifecycle, escrow, payouts, disputes, freelancer assignment, or XP side effects.'
argument-hint: 'Describe the quest-flow change to verify'
---

# Quest Flow Regression

## When to Use
- Quest lifecycle changes
- Escrow or payout logic changes
- Dispute settlement changes
- Assignment, completion, or XP hooks change

## Procedure
1. Identify where the change touches quest states, wallet state, notifications, and XP.
2. Verify that state transitions still follow the expected sequence.
3. Check for duplicate side effects, missing transaction boundaries, and missing notifications.
4. Update or add regression tests around the changed branch.
5. Validate frontend contract changes if visible quest fields or statuses moved.

## Done Criteria
- Core register -> create quest -> apply -> assign -> complete -> pay path still holds
- Side effects happen once and in the correct order
- Regression coverage exists for the changed branch
