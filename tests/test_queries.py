"""Tests for the stakeholder queries and data-quality checks in db/queries.sql."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = (ROOT / "db" / "queries.sql").read_text(encoding="utf-8")


def _query(label, next_label):
    """Return one query from db/queries.sql, without its title comment line."""
    block = QUERIES.split(f"-- {label}.")[1].split(f"-- {next_label}.")[0]
    return block.split("\n", 1)[1]  # drop the rest of the title line


def _add_sample_order(cur, code, quantity, defective):
    """Synthetic test fixture: one completed order with one finished stage."""
    cur.execute(
        """
        INSERT INTO orders (order_code, box_type_id, quantity, received_at,
                            material_in_stock, open_orders_at_receipt, entered_by,
                            completed_at)
        VALUES (%s, 1, %s, '2026-10-20 09:00', true, 0, 'test', '2026-10-22 09:00')
        RETURNING order_id;
        """,
        (code, quantity),
    )
    order_id = cur.fetchone()["order_id"]
    cur.execute(
        """
        INSERT INTO stage_events (order_id, stage_id, machine_id, started_at, finished_at,
                                  boxes_completed, boxes_defective, entered_by)
        VALUES (%s,
                (SELECT stage_id FROM stages WHERE code = 'CORRUGATE'),
                (SELECT machine_id FROM machines WHERE code = 'M01'),
                '2026-10-20 10:00', '2026-10-20 12:00', %s, %s, 'test');
        """,
        (order_id, quantity, defective),
    )


def test_all_queries_run_on_sample_data(db_cursor):
    _add_sample_order(db_cursor, "Q-1", 1000, 20)
    db_cursor.execute(QUERIES)  # raises if any query is invalid


def test_defect_rate_is_averaged_per_order(db_cursor):
    # 2% and 4% defect rates -> average 3%
    _add_sample_order(db_cursor, "Q-1", 1000, 20)
    _add_sample_order(db_cursor, "Q-2", 500, 20)
    db_cursor.execute(_query("Q3", "Q4"))
    row = db_cursor.fetchone()
    assert float(row["avg_defect_rate_pct"]) == 3.0
    assert row["orders"] == 2


def test_lead_time_query_reports_completed_orders(db_cursor):
    _add_sample_order(db_cursor, "Q-1", 1000, 0)
    db_cursor.execute(_query("Q4", "Q5"))
    row = db_cursor.fetchone()
    assert float(row["avg_lead_days"]) == 2.0