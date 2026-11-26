# Checkpoint 1 – Data Collection MVP

## Project approval

Approved by the Module Leader by email on 19 October 2026 (UDE5014CM project scope).
The approval email is retained by the student as the approval record.

## Component delivered

An independently runnable data-collection component: a Flask web application connected
to PostgreSQL that accepts new orders and production stage records, validates them,
stores them with provenance (who, when, how and from where), and lets the user retrieve
them on the orders list and order detail pages.

## Stakeholder value statement

This component enables the **workshop manager** to **record each order and production stage
as it happens or at the end of the day** by a **mobile-friendly web form that validates the
input and stores it in PostgreSQL with time and source information**, resulting in **a reliable,
timestamped production record that replaces partial notes and makes stage durations and
defects measurable for the first time**.

## Acceptance criteria (issue #1)

| Criterion | Result |
|---|---|
| Manager can create a new order and stage event through a web form | Passed |
| Invalid input is rejected with an error message | Passed |
| Each record is saved with event time, entry time, entered_by and source | Passed |
| Saved records can be viewed on a list page | Passed |
| At least 3 automated tests (valid, invalid, persistence/provenance) | Passed (20 tests) |

## Test specification

- **Purpose:** verify that the collection component accepts valid input, rejects invalid
  input, and persists records with provenance.
- **Inputs:** synthetic order and stage form data (valid and invalid cases) in a separate
  test database.
- **Expected outputs:** valid records saved with `entered_by`, `source = web_form` and
  `created_at`; invalid records rejected with a field error and not saved; invalid
  stage/machine pairs blocked by the database.
- **Start commands:** see README sections 1–3.
- **Test command:** `python -m pytest -v`
- **Acceptance criteria:** all tests pass.
- **Actual result:** 20 passed.

## Substantive changes during this checkpoint

- #1 Data collection MVP: schema, order and stage forms, validation, list and detail pages, tests.
- #2 Defect found in manual testing: order codes differing only by letter case were accepted
  as different orders. Fixed by normalising codes to uppercase and adding a case-insensitive
  unique index.
- #3 Machines restricted by stage (database foreign key, server validation and filtered form);
  orders list shows status and stage progress.
- #4 Stage editing added so a stage can be finished later; original provenance is preserved
  and `updated_by` / `updated_at` are recorded.

## Known limitations and next steps

- Order completion (`completed_at`) is not yet recorded through the interface.
- Downtime events and material deliveries are planned for Checkpoint 2.
- Stage order by box-type route (with warnings) is planned for Checkpoint 2.
- The interface is in English; an Uzbek version is planned before data collection starts.
- Machine and stage reference data must be confirmed with the workshop manager.