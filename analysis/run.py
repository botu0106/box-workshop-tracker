"""Run the whole analysis and write the report.

    python -m analysis.run                  # real data from the database in .env / DATABASE_URL
    python -m analysis.run --synthetic 60   # synthetic data, only to test the code

Output: analysis_output/report.md, results.json and the figures.
Run it again whenever new data has been collected: everything is recalculated.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from . import data, models, plots, stats
from .synthetic import make_tables

DEFAULT_OUT = "analysis_output"


def load_real_tables():
    import psycopg2
    import psycopg2.extras

    from app import create_app

    settings = create_app().config["DB"]
    conn = psycopg2.connect(**settings, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        return data.load_tables(conn)
    finally:
        conn.close()


def analyse(tables, out_dir, synthetic=False):
    stages = data.build_stages(tables)
    orders = data.build_orders(tables, stages)
    evaluation = models.evaluate(orders)
    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "synthetic_data": synthetic,
        "data_quality": data.data_quality(orders, stages),
        "tests": stats.run_all(orders, stages),
        "prediction": {k: v for k, v in evaluation.items() if not k.startswith("_")},
        "robustness": models.robustness(orders),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results["figures"] = [Path(f).name for f in plots.make_all(orders, stages, evaluation, out)]
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(render_report(results), encoding="utf-8")
    return results


def _p(value):
    return "< 0.001" if value < 0.001 else f"= {value}"


def _test_line(t):
    if t["status"] == "no_variation":
        return f"- **{t['question']}**: all values are the same, nothing to test."
    if t["status"] != "ok":
        return f"- **{t['question']}**: not enough data (group sizes: {t['group_sizes']})."
    verdict = "significant" if t["significant"] else "not significant"
    detail = f"r = {t['r']}" if "r" in t else f"statistic = {t['statistic']}"
    return (f"- **{t['question']}**: {t['test']}, {detail}, p {_p(t['p_value'])} "
            f"({verdict} at α = 0.05). Group sizes: {t['group_sizes']}.")


def render_report(r):
    lines = ["# Analysis report", ""]
    if r["synthetic_data"]:
        lines += ["> **SYNTHETIC DATA – generated only to test the analysis code. "
                  "These numbers are not findings about the workshop.**", ""]
    q = r["data_quality"]
    lines += [
        f"Generated: {r['generated_at']}", "",
        "## Data", "",
        f"- Orders: {q['orders']} (completed: {q['completed_orders']})",
        f"- Stage records: {q['stage_records']} (finished: {q['finished_stages']})",
        f"- Stage durations excluded as implausible (< {data.MIN_PLAUSIBLE_STAGE_MINUTES} min): "
        f"{q['implausible_durations']}",
        f"- Orders with a recorded material arrival time: {q['material_waits_recorded']}",
        f"- Share of stage records entered later: {q['late_entry_share']}",
        f"- Collection period: {q['first_order']} – {q['last_order']}", "",
        "## Hypothesis tests", "",
    ]
    tests = r["tests"]
    lines.append(_test_line(tests["lead_time_by_material"]))
    lines.append(_test_line(tests["defect_rate_by_box_type"]))
    lines.append(_test_line(tests["quantity_vs_lead_time"]))
    lines.append(_test_line(tests["material_wait_vs_lead_time"]))
    lines += [_test_line(t) for t in tests["duration_by_operators"]] or [
        "- Stage duration by operators: no stages with operator counts yet."]
    lines += ["", "Tests show association, not cause. With small samples the normality "
              "check has little power and a non-significant result does not show that "
              "there is no effect.", "", "## Lead-time prediction", ""]

    p = r["prediction"]
    if p["status"] != "ok":
        lines.append(f"Not enough completed orders yet ({p['completed_orders']} of at least "
                     f"{p['needed']} needed). {p['note']}")
    else:
        lines += [
            f"Chronological split: {p['train_orders']} training orders (all completed before "
            f"{p['test_period_starts'][:16]}), {p['test_orders']} test orders. "
            "Features are only those known at receipt; the material waiting time is "
            "known later and is therefore not used for prediction.", "",
            "| Model | MAE (days) | MAE 95% CI | RMSE | Within ±1 day |",
            "|---|---|---|---|---|",
        ]
        for name, m in p["results"].items():
            lines.append(f"| {name} | {m['MAE']} | {m['MAE_95_CI']} | {m['RMSE']} | "
                         f"{100 * m['within_1_day']:.0f}% |")
        lines += ["", f"Best model: **{p['best_model']}**, "
                  f"{100 * p['improvement_over_baseline']:.1f}% lower MAE than the baseline "
                  f"(target 15%: {'met' if p['target_15pct_met'] else 'not met'})."]
    lines += ["", "## Robustness checks", ""]
    for name, c in r["robustness"].items():
        if c["status"] != "ok":
            lines.append(f"- {name}: not enough data.")
        else:
            lines.append(f"- {name}: best = {c['best_model']}, MAE = {c['MAE']}")
    lines += ["", "## Figures", ""] + [f"![{f}]({f})" for f in r["figures"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--synthetic", type=int, metavar="N",
                        help="use N synthetic orders instead of the database (testing only)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="output folder")
    args = parser.parse_args()

    if args.synthetic:
        tables = make_tables(args.synthetic)
        out = args.out if args.out != DEFAULT_OUT else "analysis_output_synthetic"
    else:
        tables = load_real_tables()
        out = args.out
    results = analyse(tables, out, synthetic=bool(args.synthetic))
    q = results["data_quality"]
    print(f"Orders: {q['orders']}, completed: {q['completed_orders']}, "
          f"prediction: {results['prediction']['status']}")
    print(f"Report written to {Path(out) / 'report.md'}")


if __name__ == "__main__":
    main()
