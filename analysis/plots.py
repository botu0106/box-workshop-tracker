"""Figures for the analysis report. Each function saves one PNG and returns its path,
or None when there is not enough data for that figure."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt  # noqa: E402

BLUE = "#257de0"
ORANGE = "#f47230"
GRID = "#e5e5e5"
TEXT = "#333333"


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=12, color=TEXT)
    ax.set_xlabel(xlabel, color=TEXT)
    ax.set_ylabel(ylabel, color=TEXT)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _save(fig, out_dir, name):
    path = Path(out_dir) / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def _boxplot(ax, groups, labels):
    parts = ax.boxplot(groups, tick_labels=labels, patch_artist=True, widths=0.5)
    for box in parts["boxes"]:
        box.set(facecolor=BLUE, alpha=0.35, edgecolor=BLUE)
    for median in parts["medians"]:
        median.set(color=BLUE, linewidth=2)


def collection_progress(stages, orders, out_dir):
    if orders.empty:
        return None
    per_day = orders.set_index("received_at").resample("D")["order_id"].count().cumsum()
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(per_day.index, per_day.values, color=BLUE, linewidth=2, marker="o", markersize=4)
    _style(ax, "Orders collected (cumulative)", "Date received", "Orders")
    fig.autofmt_xdate()
    return _save(fig, out_dir, "01_collection_progress.png")


def stage_durations(stages, out_dir):
    data = stages[stages["duration_plausible"]]
    groups = [(s, g["duration_hours"].to_numpy()) for s, g in data.groupby("stage") if len(g) >= 2]
    if not groups:
        return None
    groups.sort(key=lambda item: -float(sorted(item[1])[len(item[1]) // 2]))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _boxplot(ax, [g for _, g in groups], [s for s, _ in groups])
    _style(ax, "Stage duration (finished stages)", "", "Hours")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    return _save(fig, out_dir, "02_stage_durations.png")


def lead_time_by_box_type(orders, out_dir):
    done = orders[orders["completed"]]
    groups = [(b, g["lead_days"].to_numpy()) for b, g in done.groupby("box_type") if len(g) >= 2]
    if not groups:
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    _boxplot(ax, [g for _, g in groups], [b for b, _ in groups])
    _style(ax, "Order lead time by box type", "", "Days")
    return _save(fig, out_dir, "03_lead_time_by_box_type.png")


def lead_time_by_material(orders, out_dir):
    done = orders[orders["completed"]]
    groups = [
        ("in stock", done.loc[done["material_in_stock"], "lead_days"].to_numpy()),
        ("not in stock", done.loc[~done["material_in_stock"], "lead_days"].to_numpy()),
    ]
    if any(len(g) < 2 for _, g in groups):
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    parts = ax.boxplot([g for _, g in groups], tick_labels=[l for l, _ in groups],
                       patch_artist=True, widths=0.5)
    for box, color in zip(parts["boxes"], (BLUE, ORANGE)):
        box.set(facecolor=color, alpha=0.35, edgecolor=color)
    for median, color in zip(parts["medians"], (BLUE, ORANGE)):
        median.set(color=color, linewidth=2)
    _style(ax, "Lead time: material in stock at receipt?", "", "Days")
    return _save(fig, out_dir, "04_lead_time_by_material.png")


def defect_rate_by_box_type(orders, out_dir):
    data = orders.dropna(subset=["defect_rate"])
    if data.empty:
        return None
    summary = data.groupby("box_type")["defect_rate"].agg(["mean", "count"]).sort_values("mean")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(summary.index, 100 * summary["mean"], color=BLUE, height=0.55)
    for y, (value, n) in enumerate(zip(100 * summary["mean"], summary["count"])):
        ax.text(value, y, f"  {value:.1f}%  (n={n})", va="center", color=TEXT, fontsize=9)
    _style(ax, "Average order defect rate by box type", "Defective boxes, % of order", "")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    return _save(fig, out_dir, "05_defect_rate_by_box_type.png")


def machine_busy_hours(stages, out_dir):
    data = stages[stages["duration_plausible"] & stages["machine"].notna()]
    if data.empty:
        return None
    hours = data.groupby("machine")["duration_hours"].sum().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(hours.index, hours.values, color=BLUE, width=0.6)
    _style(ax, "Recorded busy hours per machine", "Machine", "Hours")
    return _save(fig, out_dir, "06_machine_busy_hours.png")


def predicted_vs_actual(evaluation, out_dir):
    if evaluation.get("status") != "ok":
        return None
    test = evaluation["_test"]
    best = evaluation["best_model"]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(test["lead_days"], test[f"pred: {best}"], color=BLUE, s=40, label=best)
    ax.scatter(test["lead_days"], test["pred: baseline (median by box type)"],
               color=ORANGE, s=40, marker="s", label="baseline")
    low = min(test["lead_days"].min(), 0)
    high = test["lead_days"].max() * 1.1
    ax.plot([low, high], [low, high], color="#999999", linewidth=1, linestyle="--")
    _style(ax, "Predicted vs actual lead time (test set)", "Actual days", "Predicted days")
    ax.legend(frameon=False)
    return _save(fig, out_dir, "07_predicted_vs_actual.png")


def make_all(orders, stages, evaluation, out_dir):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    figures = [
        collection_progress(stages, orders, out_dir),
        stage_durations(stages, out_dir),
        lead_time_by_box_type(orders, out_dir),
        lead_time_by_material(orders, out_dir),
        defect_rate_by_box_type(orders, out_dir),
        machine_busy_hours(stages, out_dir),
        predicted_vs_actual(evaluation, out_dir),
    ]
    return [f for f in figures if f]
