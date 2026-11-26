"""Lead-time estimate for a new order, used by the dashboard.

The model is chosen the same way as in the analysis report: every model is scored on a
chronological test set, and the best one is then refitted on all completed orders.
With too few completed orders the estimate falls back to the median lead time of the
same box type, and says so.
"""
import pandas as pd

from . import models

MIN_FOR_BASELINE = 1


def predict_lead_time(orders, new_order):
    """new_order: dict with box_code, finishing, quantity, material_in_stock,
    open_orders_at_receipt (all known when the order is received)."""
    done = orders[orders["completed"]].dropna(subset=[models.TARGET])
    same_type = done[done["box_code"] == new_order["box_code"]]
    if len(done) < MIN_FOR_BASELINE:
        return {"status": "no_data", "completed_orders": 0}

    X_new = models._features(pd.DataFrame([new_order]))
    evaluation = models.evaluate(orders)
    if evaluation["status"] == "ok":
        name = evaluation["best_model"]
        model = models.make_models()[name]
        model.fit(models._features(done), done[models.TARGET].to_numpy())
        days = float(model.predict(X_new)[0])
        return {
            "status": "ok",
            "days": round(max(days, 0.0), 1),
            "method": name,
            "test_mae": evaluation["results"][name]["MAE"],
            "completed_orders": int(len(done)),
        }

    baseline = models.MedianByBoxType().fit(models._features(done), done[models.TARGET].to_numpy())
    return {
        "status": "baseline_only",
        "days": round(float(baseline.predict(X_new)[0]), 1),
        "method": "median by box type",
        "same_type_orders": int(len(same_type)),
        "completed_orders": int(len(done)),
        "needed_for_models": models.MIN_TRAIN + models.MIN_TEST,
    }
