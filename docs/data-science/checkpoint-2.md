# Checkpoint 2 – Reliable Collection and Data Quality

## Component delivered

The collection and data-management component is now deployed online so the workshop
manager can use it from another city. Data entry requires login, the person who enters
or edits a record is taken from the logged-in user, and the interface is in Uzbek.
Stakeholder queries and data-quality checks are provided in `db/queries.sql`.

## Stakeholder value statement

This component enables the **workshop owner** to **see open orders, stage durations,
defect rates, lead times, orders at risk of missing their promised date and machine
usage** by **running the queries in `db/queries.sql` on data collected through the
online form**, resulting in **production problems that were previously only described
verbally becoming measurable once data entry is under way**.

## Substantive changes since Checkpoint 1

- #7 Login with hashed passwords; all data pages require login; `entered_by` and
  `updated_by` come from the logged-in user, so records cannot be entered under another name.
- #8 Online deployment: web service on Render, PostgreSQL on Neon (Render's free database
  expires after 30 days). Secrets are only in platform environment variables; the local
  setup still works without any cloud service.
- #9 Uzbek interface, validation messages and reference data.
- Reference data corrected after review by the workshop manager on 12 Nov 2026: the
  "kleyval" layer-gluing stage and machine, a separate pressing stage, final gluing always
  manual, one machine of each type. Wrong stage–machine pairs are removed only if no
  records use them.
- Order completion with validation (no unfinished stages, not before receipt or the last
  stage, not in the future), `completed_by`, and reopening.
- Database scripts are safe to run more than once; schema changes are applied with
  `ALTER TABLE ... IF NOT EXISTS` so existing databases stay in step.
- Stakeholder queries (Q1–Q6) and data-quality checks (DQ1–DQ4) in `db/queries.sql`.

## Data collection status and stakeholder feedback

Data collection did not produce records in this period. The manager tried the system
but found the stage form too slow to use alongside his work, and internet access at the
workshop was unreliable. He asked for a much simpler interface. In response:

- defects found during testing were recorded (duplicate stages, box counts above the
  order quantity);
- the next change (issue #5) replaces the stage form with a route checklist per box type:
  one button to start and one to finish each stage, machines filled in automatically,
  each stage recorded once, and automatic order completion when the final stage ends.

Because collection has started later than planned, a revised minimum data target will be
agreed with the Module Leader.

## Tests

- **Command:** `python -m pytest -v`
- **Result:** 29 passed (validation, persistence and provenance, duplicates, a database
  constraint, access control and password hashing, stakeholder queries).
- Query tests use synthetic fixtures in the separate test database.

## Known limitations and next steps

- No genuine records yet; collection restarts with the simplified interface.
- Route checklist (#5), duplicate-stage and quantity checks, material waiting time (#6).
- Downtime events and an audit log are planned for later checkpoints.