"""Database operations shared by the web pages and the JSON API.

Each function runs one change in one transaction. The callers validate the input
first (app/validation.py) and decide how to show the result: a page or JSON.
"""
from .db import get_db

ORDER_SELECT = """
    SELECT o.*, b.name AS box_type, b.code AS box_code
    FROM orders o
    JOIN box_types b ON b.box_type_id = o.box_type_id
"""

# Workload at receipt: orders already received and not yet completed at that moment
OPEN_ORDERS_AT = """
    (SELECT COUNT(*) FROM orders o2
     WHERE o2.order_id <> COALESCE(%(order_id)s, -1)
       AND o2.received_at <= %(received_at)s
       AND (o2.completed_at IS NULL OR o2.completed_at > %(received_at)s))
"""


def create_order(data, source):
    """Insert a validated order and return its id. Raises UniqueViolation on a duplicate code."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO orders (
                    order_code, box_type_id, quantity, received_at, promised_date,
                    material_in_stock, material_received_at, finishing,
                    open_orders_at_receipt, entered_by, source
                )
                VALUES (
                    %(order_code)s, %(box_type_id)s, %(quantity)s, %(received_at)s, %(promised_date)s,
                    %(material_in_stock)s, %(material_received_at)s, %(finishing)s,
                    {OPEN_ORDERS_AT}, %(entered_by)s, %(source)s
                )
                RETURNING order_id;
                """,
                {**data, "order_id": None, "source": source},
            )
            order_id = cur.fetchone()["order_id"]
        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise


def update_order(order_id, data):
    """Update a validated order; the editor is stored in updated_by."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE orders
                SET order_code           = %(order_code)s,
                    box_type_id          = %(box_type_id)s,
                    quantity             = %(quantity)s,
                    received_at          = %(received_at)s,
                    promised_date        = %(promised_date)s,
                    material_in_stock    = %(material_in_stock)s,
                    material_received_at = %(material_received_at)s,
                    finishing            = %(finishing)s,
                    open_orders_at_receipt = {OPEN_ORDERS_AT},
                    updated_by           = %(entered_by)s,
                    updated_at           = now()
                WHERE order_id = %(order_id)s;
                """,
                {**data, "order_id": order_id},
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def delete_order(order_id):
    """Delete an order together with its stage records. Returns False if it did not exist."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stage_events WHERE order_id = %s;", (order_id,))
            cur.execute("DELETE FROM orders WHERE order_id = %s RETURNING order_id;", (order_id,))
            deleted = cur.fetchone() is not None
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise


def start_stage(order_id, stage_id, machine_id, started_at, entry_mode, username, source):
    """Record the start of a stage. Raises UniqueViolation if the stage was already started."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stage_events (
                    order_id, stage_id, machine_id, started_at, entry_mode, entered_by, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING stage_event_id;
                """,
                (order_id, stage_id, machine_id, started_at, entry_mode, username, source),
            )
            stage_event_id = cur.fetchone()["stage_event_id"]
        conn.commit()
        return stage_event_id
    except Exception:
        conn.rollback()
        raise


def finish_stage(stage_event_id, data, late):
    """Record the finish of a started stage (validated data)."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE stage_events
            SET finished_at     = %(finished_at)s,
                boxes_completed = %(boxes_completed)s,
                boxes_defective = %(boxes_defective)s,
                operators       = %(operators)s,
                entry_mode      = CASE WHEN %(late)s THEN 'end_of_day' ELSE entry_mode END
            WHERE stage_event_id = %(stage_event_id)s;
            """,
            {**data, "late": late, "stage_event_id": stage_event_id},
        )
    conn.commit()


def delete_stage_event(stage_event_id):
    """Undo a recorded stage. The order is reopened if it had been completed."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM stage_events WHERE stage_event_id = %s RETURNING order_id;",
                (stage_event_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None
            cur.execute(
                "UPDATE orders SET completed_at = NULL, completed_by = NULL WHERE order_id = %s;",
                (row["order_id"],),
            )
        conn.commit()
        return row["order_id"]
    except Exception:
        conn.rollback()
        raise


def complete_if_all_finished(order, route, username):
    """Mark the order completed when every stage of its route is finished."""
    if not route or not all(stage["finished_at"] for stage in route):
        return False
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orders SET completed_at = %s, completed_by = %s
            WHERE order_id = %s AND completed_at IS NULL;
            """,
            (max(stage["finished_at"] for stage in route), username, order["order_id"]),
        )
    conn.commit()
    return True
