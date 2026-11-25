"""Order lead-time prediction: a baseline and two models, validated chronologically.

Only information known when an order is received is used as features, and a model
is trained only on orders that had already been COMPLETED before the first order
it is tested on was received. This is the "no leakage" rule from the Module
Leader's feedback: at prediction time the system cannot know the future.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

FEATURES_CATEGORICAL = ["box_code", "finishing"]
FEATURES_NUMERIC = ["quantity", "open_orders_at_receipt", "material_in_stock"]
TARGET = "lead_days"
MIN_TRAIN = 8
MIN_TEST = 3
RANDOM_STATE = 0


def chronological_split(orders, test_share=0.3):
    """Split completed orders by receipt time without leaking future outcomes.

    The last `test_share` of completed orders (by received_at) form the test set.
    The training set holds only orders completed before the first test order was
    received, so every training outcome was known at prediction time.
    """
    done = orders[orders["completed"]].dropna(subset=[TARGET]).sort_values("received_at")
    n_test = max(MIN_TEST, int(round(len(done) * test_share)))
    if len(done) < MIN_TRAIN + MIN_TEST:
        return None, None, None
    test = done.iloc[-n_test:]
    cutoff = test["received_at"].min()
    train = done[done["completed_at"] < cutoff]
    if len(train) < MIN_TRAIN:
        return None, None, cutoff
    return train, test, cutoff


class MedianByBoxType:
    """Baseline: predict the median lead time of the same box type in training data."""

    def fit(self, X, y):
        frame = X.assign(_y=np.asarray(y))
        self.medians_ = frame.groupby("box_code")["_y"].median().to_dict()
        self.overall_ = float(np.median(y))
        return self

    def predict(self, X):
        return X["box_code"].map(self.medians_).fillna(self.overall_).to_numpy()


def _pipeline(estimator):
    preprocess = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore"), FEATURES_CATEGORICAL),
        ("numbers", "passthrough", FEATURES_NUMERIC),
    ])
    return Pipeline([("prepare", preprocess), ("model", estimator)])


def make_models():
    return {
        "baseline (median by box type)": MedianByBoxType(),
        "linear regression": _pipeline(LinearRegression()),
        "random forest": _pipeline(RandomForestRegressor(
            n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE,
        )),
    }


def _features(frame):
    X = frame[FEATURES_CATEGORICAL + FEATURES_NUMERIC].copy()
    X["material_in_stock"] = X["material_in_stock"].astype(int)
    return X


def metrics(y_true, y_pred):
    err = np.asarray(y_pred) - np.asarray(y_true)
    return {
        "MAE": round(float(np.mean(np.abs(err))), 3),
        "RMSE": round(float(np.sqrt(np.mean(err ** 2))), 3),
        "within_1_day": round(float(np.mean(np.abs(err) <= 1)), 3),
    }


def bootstrap_mae_ci(y_true, y_pred, n=1000, seed=RANDOM_STATE):
    """95% bootstrap confidence interval for the MAE on the test set."""
    rng = np.random.default_rng(seed)
    errors = np.abs(np.asarray(y_pred) - np.asarray(y_true))
    samples = [errors[rng.integers(0, len(errors), len(errors))].mean() for _ in range(n)]
    low, high = np.percentile(samples, [2.5, 97.5])
    return [round(float(low), 3), round(float(high), 3)]


def evaluate(orders, test_share=0.3):
    """Train every model on the chronological training set and score it on the test set."""
    train, test, cutoff = chronological_split(orders, test_share)
    completed = int(orders["completed"].sum())
    if train is None:
        return {
            "status": "insufficient_data",
            "completed_orders": completed,
            "needed": MIN_TRAIN + MIN_TEST,
            "note": f"At least {MIN_TRAIN} training and {MIN_TEST} test orders are needed, "
                    "with training orders completed before the test period starts.",
        }

    X_train, X_test = _features(train), _features(test)
    y_train, y_test = train[TARGET].to_numpy(), test[TARGET].to_numpy()
    results, predictions = {}, {}
    for name, model in make_models().items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        predictions[name] = pred
        results[name] = {**metrics(y_test, pred), "MAE_95_CI": bootstrap_mae_ci(y_test, pred)}

    baseline_mae = results["baseline (median by box type)"]["MAE"]
    best = min(results, key=lambda k: results[k]["MAE"])
    improvement = (baseline_mae - results[best]["MAE"]) / baseline_mae if baseline_mae else 0.0
    return {
        "status": "ok",
        "train_orders": int(len(train)),
        "test_orders": int(len(test)),
        "test_period_starts": str(cutoff),
        "results": results,
        "best_model": best,
        "improvement_over_baseline": round(float(improvement), 3),
        "target_15pct_met": bool(improvement >= 0.15),
        "_test": test.assign(**{f"pred: {k}": v for k, v in predictions.items()}),
    }


def robustness(orders):
    """Repeat the evaluation under the checks named in the proposal."""
    checks = {}
    first_week_end = orders["received_at"].min() + pd.Timedelta(days=7) if len(orders) else None
    variants = {
        "test share 20%": (orders, 0.2),
        "test share 40%": (orders, 0.4),
        "excluding first collection week": (
            orders[orders["received_at"] >= first_week_end] if first_week_end is not None else orders, 0.3,
        ),
    }
    done = orders[orders["completed"]]
    if len(done) >= 4:
        q1, q3 = done[TARGET].quantile([0.25, 0.75])
        limit = q3 + 3 * (q3 - q1)
        variants["excluding extreme lead times"] = (
            orders[~orders["completed"] | (orders[TARGET] <= limit)], 0.3,
        )
    for name, (frame, share) in variants.items():
        res = evaluate(frame, share)
        if res["status"] != "ok":
            checks[name] = {"status": res["status"]}
        else:
            checks[name] = {
                "status": "ok",
                "best_model": res["best_model"],
                "MAE": {k: v["MAE"] for k, v in res["results"].items()},
            }
    return checks
