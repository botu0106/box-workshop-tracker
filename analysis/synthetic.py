"""Synthetic data used ONLY to test the analysis code.

It has the same columns as the real database tables. Every report made from it is
labelled as synthetic; its numbers are never findings about the workshop.
"""
import numpy as np
import pandas as pd

ROUTES = {
    "PLAIN": ["CORRUGATE", "MOUNT", "PRESS", "DIECUT", "GLUING"],
    "STENCIL": ["CORRUGATE", "MOUNT", "PRESS", "STENCIL", "DIECUT", "GLUING"],
    "OFFSET": ["PAPERCUT", "OFFSET", "DRYING", "CORRUGATE", "MOUNT", "PRESS", "DIECUT", "GLUING"],
    "MICRO": ["PAPERCUT", "OFFSET", "DRYING", "DIECUT", "GLUING"],
}
MACHINES = {"CORRUGATE": "M01", "PAPERCUT": "M02", "STENCIL": "M03", "OFFSET": "M04",
            "PRESS": "M07", "DIECUT": "M08", "MOUNT": "M09", "GLUING": "M10"}


def make_tables(n_orders=60, seed=0, start="2026-11-16 09:00"):
    rng = np.random.default_rng(seed)
    orders, stages = [], []
    received = pd.Timestamp(start)
    event_id = 1
    for order_id in range(1, n_orders + 1):
        received += pd.Timedelta(hours=float(rng.uniform(1, 6)))
        box = rng.choice(list(ROUTES))
        quantity = int(rng.choice([1000, 1500, 2000, 3000]))
        in_stock = bool(rng.random() < 0.7)
        clock = received + pd.Timedelta(days=0 if in_stock else float(rng.uniform(1, 3)))
        material_received = None if in_stock else clock
        defective_total = 0
        for code in ROUTES[box]:
            hours = float(rng.uniform(0.5, 3)) * quantity / 1000
            if code == "DRYING":
                hours = 20.0
            started, finished = clock, clock + pd.Timedelta(hours=hours)
            defective = int(rng.binomial(quantity, 0.01)) if code in ("DIECUT", "GLUING") else 0
            defective_total += defective
            stages.append({
                "stage_event_id": event_id, "order_id": order_id, "stage_code": code,
                "stage": code.title(), "machine": MACHINES.get(code), "started_at": started,
                "finished_at": finished, "operators": int(rng.choice([1, 2])),
                "boxes_completed": quantity, "boxes_defective": defective,
                "entry_mode": rng.choice(["realtime", "end_of_day"]), "created_at": finished,
            })
            event_id += 1
            clock = finished + pd.Timedelta(hours=float(rng.uniform(0.5, 8)))
        orders.append({
            "order_id": order_id, "order_code": f"S-{order_id}", "box_code": box,
            "box_type": box.title(), "quantity": quantity, "received_at": received,
            "promised_date": None, "material_in_stock": in_stock,
            "material_received_at": material_received, "finishing": "none",
            "open_orders_at_receipt": int(rng.integers(0, 6)), "completed_at": clock,
            "created_at": received,
        })
    return {"orders": pd.DataFrame(orders), "stages": pd.DataFrame(stages)}
