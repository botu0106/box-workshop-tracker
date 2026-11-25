"""Load the collected data from PostgreSQL and build the analysis datasets.

Two datasets are built:
- stages: one row per recorded production stage (duration, defects, machine...)
- orders: one row per order, with only the information known when the order
  was received (the prediction features) plus its outcomes (lead time, defect rate).
"""
import pandas as pd

# A stage shorter than this was almost certainly entered after the fact without
# real times (e.g. started and finished one minute apart), so its duration is not used.
MIN_PLAUSIBLE_STAGE_MINUTES = 5

TABLE_QUERIES = {
    "orders": """
        SELECT o.order_id, o.order_code, b.code AS box_code, b.name AS box_type,
               o.quantity, o.received_at, o.promised_date, o.material_in_stock,
               o.material_received_at,
               o.finishing, o.open_orders_at_receipt, o.completed_at, o.created_at
        FROM orders o JOIN box_types b USING (box_type_id)
    """,
    "stages": """
        SELECT se.stage_event_id, se.order_id, s.code AS stage_code, s.name AS stage,
               m.code AS machine, se.started_at, se.finished_at, se.operators,
               se.boxes_completed, se.boxes_defective, se.entry_mode, se.created_at
        FROM stage_events se
        JOIN stages s USING (stage_id)
        LEFT JOIN machines m USING (machine_id)
    """,
}


def load_tables(conn):
    """Read orders and stage events from the database into DataFrames."""
    tables = {}
    for name, sql in TABLE_QUERIES.items():
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            columns = [c.name for c in cur.description]
        tables[name] = pd.DataFrame(rows, columns=columns)
    return tables


def _to_local(series):
    """Timestamps from the database -> Tashkent time without timezone."""
    series = pd.to_datetime(series)
    if series.dt.tz is not None:
        series = series.dt.tz_convert("Asia/Tashkent").dt.tz_localize(None)
    return series


def build_stages(tables):
    stages = tables["stages"].copy()
    for col in ("started_at", "finished_at", "created_at"):
        stages[col] = _to_local(stages[col])
    stages["duration_hours"] = (
        (stages["finished_at"] - stages["started_at"]).dt.total_seconds() / 3600
    )
    stages["duration_plausible"] = stages["duration_hours"] * 60 >= MIN_PLAUSIBLE_STAGE_MINUTES
    stages["defect_rate"] = stages["boxes_defective"] / stages["boxes_completed"].where(
        stages["boxes_completed"] > 0
    )
    return stages


def build_orders(tables, stages=None):
    """One row per order with features known at receipt and its outcomes.

    lead_days   = completed_at - received_at (only for completed orders)
    defect_rate = all defective boxes recorded on the order's stages / ordered quantity.
                  The order is the unit, so repeated stage records of one order
                  count once (as the Module Leader asked).
    """
    if stages is None:
        stages = build_stages(tables)
    orders = tables["orders"].copy()
    for col in ("received_at", "completed_at", "created_at", "material_received_at"):
        orders[col] = _to_local(orders[col])
    orders["material_in_stock"] = orders["material_in_stock"].astype(bool)
    orders["completed"] = orders["completed_at"].notna()
    orders["lead_days"] = (
        (orders["completed_at"] - orders["received_at"]).dt.total_seconds() / 86400
    )
    # Days spent waiting for missing material. Known only after the order was received,
    # so it is used to explain delays, never as a prediction feature.
    orders["material_wait_days"] = (
        (orders["material_received_at"] - orders["received_at"]).dt.total_seconds() / 86400
    )

    per_order = stages.groupby("order_id").agg(
        stages_recorded=("stage_event_id", "count"),
        stages_finished=("finished_at", "count"),
        boxes_defective=("boxes_defective", "sum"),
        late_entries=("entry_mode", lambda s: (s == "end_of_day").sum()),
    ).reset_index()
    orders = orders.merge(per_order, on="order_id", how="left")
    for col in ("stages_recorded", "stages_finished", "boxes_defective", "late_entries"):
        orders[col] = orders[col].fillna(0).astype(int)
    orders["defect_rate"] = (orders["boxes_defective"] / orders["quantity"]).where(
        orders["stages_finished"] > 0
    )
    return orders.sort_values("received_at").reset_index(drop=True)


def data_quality(orders, stages):
    """Counts reported at the top of the analysis report."""
    return {
        "orders": int(len(orders)),
        "completed_orders": int(orders["completed"].sum()),
        "stage_records": int(len(stages)),
        "finished_stages": int(stages["finished_at"].notna().sum()),
        "implausible_durations": int(
            (stages["finished_at"].notna() & ~stages["duration_plausible"]).sum()
        ),
        "material_waits_recorded": int(orders["material_wait_days"].notna().sum()),
        "late_entry_share": (
            round(float((stages["entry_mode"] == "end_of_day").mean()), 3) if len(stages) else None
        ),
        "first_order": f"{orders['received_at'].min():%Y-%m-%d %H:%M}" if len(orders) else None,
        "last_order": f"{orders['received_at'].max():%Y-%m-%d %H:%M}" if len(orders) else None,
    }
