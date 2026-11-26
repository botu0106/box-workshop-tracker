"""Owner dashboard: current production figures and a lead-time estimate for a new order.

Everything is recalculated from the database on every request, so a record the manager
has just entered shows up immediately.
"""
from datetime import timedelta

import pandas as pd
from flask import Blueprint, render_template, request

from analysis import data, forecast

from . import charts
from .auth import login_required
from .db import get_db
from .routes import FINISHING_BOX_TYPES, get_box_types
from .validation import local_now

bp = Blueprint("dashboard", __name__)


def _bars(series, counts=None, digits=1):
    """Rows for a horizontal bar chart drawn with plain HTML: label, value, width in %."""
    if series.empty:
        return []
    top = float(series.max()) or 1.0
    rows = []
    for label, value in series.items():
        rows.append({
            "label": label,
            "value": round(float(value), digits),
            "width": round(100 * float(value) / top, 1),
            "n": int(counts[label]) if counts is not None else None,
        })
    return rows


def summarise(orders, stages, now):
    open_orders = orders[~orders["completed"]]
    done = orders[orders["completed"]]
    week_ago = now - timedelta(days=7)
    plausible = stages[stages["finished_at"].notna() & stages["duration_plausible"]]
    recent = plausible[plausible["started_at"] >= week_ago]

    stage_hours = plausible.groupby("stage")["duration_hours"]
    defects = orders.dropna(subset=["defect_rate"]).groupby("box_type")["defect_rate"]
    busy = recent.dropna(subset=["machine"]).groupby("machine")["duration_hours"].sum().sort_index()

    # Promised today, tomorrow or already passed (orders without a promised date are skipped)
    promised = pd.to_datetime(open_orders["promised_date"], errors="coerce")
    at_risk = open_orders[promised.notna() & (promised <= pd.Timestamp(now.date() + timedelta(days=1)))]
    waiting = open_orders[~open_orders["material_in_stock"] & open_orders["material_received_at"].isna()]

    return {
        "kpi": {
            "open": int(len(open_orders)),
            "completed_week": int((done["completed_at"] >= week_ago).sum()),
            "median_lead_days": round(float(done["lead_days"].median()), 1) if len(done) else None,
            "defect_pct": (
                round(100 * float(orders["defect_rate"].mean()), 2)
                if orders["defect_rate"].notna().any() else None
            ),
            "waiting_material": int(len(waiting)),
        },
        "stage_hours": _bars(stage_hours.mean().sort_values(ascending=False), stage_hours.count()),
        "defects": _bars((100 * defects.mean()).sort_values(ascending=False), defects.count(), digits=2),
        "busy": _bars(busy),
        "at_risk": at_risk.sort_values("promised_date")[["order_id", "order_code", "promised_date"]]
        .to_dict("records"),
        "waiting": waiting[["order_id", "order_code", "received_at"]].to_dict("records"),
        "late_entry_pct": (
            round(100 * float((stages["entry_mode"] == "end_of_day").mean()), 0) if len(stages) else None
        ),
    }


MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
          "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def production(orders, now, months=6, weeks=12):
    """How many boxes the workshop produced, counted on the day each order was completed.

    good boxes = ordered quantity - defective boxes recorded on the order's stages.
    Only box counts are used: the project stores no prices, so turnover is in pieces.
    """
    done = orders[orders["completed"]].copy()
    done["good"] = (done["quantity"] - done["boxes_defective"]).clip(lower=0)
    done["month"] = done["completed_at"].dt.strftime("%Y-%m")
    done["week"] = (done["completed_at"].dt.normalize()
                    - pd.to_timedelta(done["completed_at"].dt.day_of_week, unit="D")).dt.date

    # Last N calendar months, including months with no completed orders
    month_keys = []
    year, month = now.year, now.month
    for _ in range(months):
        month_keys.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    by_month = done.groupby("month").agg(
        orders=("order_id", "count"), quantity=("quantity", "sum"),
        defective=("boxes_defective", "sum"), good=("good", "sum"),
    ).reindex(month_keys, fill_value=0)
    monthly = [
        {"label": f"{MONTHS[int(key[5:]) - 1]} {key[:4]}", **{k: int(v) for k, v in row.items()}}
        for key, row in by_month.iterrows()
    ]

    this_week = now.date() - timedelta(days=now.weekday())
    week_keys = [this_week - timedelta(weeks=w) for w in range(weeks - 1, -1, -1)]
    weekly = done.groupby("week").agg(
        orders=("order_id", "count"), defective=("boxes_defective", "sum"), good=("good", "sum"),
    ).reindex(week_keys, fill_value=0).rename_axis("week").reset_index()

    current = done[done["month"] == month_keys[0]]
    by_type = current.groupby("box_type").agg(
        orders=("order_id", "count"), good=("good", "sum"),
    ).sort_values("good", ascending=False)

    # Compare like with like: this month so far vs the same days of last month
    # (1-26 November vs 1-26 October), otherwise an unfinished month always looks worse.
    this_month = monthly[0]["good"]
    previous = done[done["month"] == month_keys[1]]
    same_days = int(previous.loc[previous["completed_at"].dt.day <= now.day, "good"].sum())
    return {
        "this_month": this_month,
        "last_month": monthly[1]["good"],
        "same_days_last_month": same_days,
        "day": now.day,
        "change_pct": round(100 * (this_month - same_days) / same_days) if same_days else None,
        "this_month_label": monthly[0]["label"],
        "monthly": monthly,
        "by_type": [{"label": t, "orders": int(r.orders), "good": int(r.good)} for t, r in by_type.iterrows()],
        "weekly_chart": charts.weekly_boxes_chart(weekly),
    }


def _forecast_input(args, box_types):
    """Read the estimate form. Returns (input dict or None, form values to show again)."""
    form = {
        "box_code": args.get("box_code", ""),
        "quantity": args.get("quantity", ""),
        "finishing": args.get("finishing", "none"),
        "material": args.get("material", "yes"),
    }
    codes = {b["code"] for b in box_types}
    try:
        quantity = int(form["quantity"])
    except ValueError:
        return None, form
    if form["box_code"] not in codes or quantity <= 0:
        return None, form
    finishing = form["finishing"] if form["box_code"] in FINISHING_BOX_TYPES else "none"
    if finishing not in ("none", "laminate", "lacquer"):
        finishing = "none"
    return {
        "box_code": form["box_code"],
        "quantity": quantity,
        "finishing": finishing,
        "material_in_stock": form["material"] == "yes",
    }, form


@bp.route("/dashboard")
@login_required
def show():
    tables = data.load_tables(get_db())
    stages = data.build_stages(tables)
    orders = data.build_orders(tables, stages)
    box_types = get_box_types()

    estimate = None
    new_order, form = _forecast_input(request.args, box_types)
    if new_order is not None:
        new_order["open_orders_at_receipt"] = int((~orders["completed"]).sum())
        estimate = forecast.predict_lead_time(orders, new_order)

    return render_template(
        "dashboard.html",
        summary=summarise(orders, stages, local_now()),
        trends=charts.make_all(orders, local_now()),
        production=production(orders, local_now()),
        box_types=box_types,
        finishing_codes=sorted(FINISHING_BOX_TYPES),
        form=form,
        estimate=estimate,
        asked=bool(request.args.get("box_code")),
    )
