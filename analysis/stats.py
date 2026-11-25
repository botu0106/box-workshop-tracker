"""Statistical tests for the analytical questions in the approved proposal.

Every test checks first whether there is enough data. With too few observations
it returns status "insufficient_data" instead of a p-value, so the report never
shows a result the data cannot support.
"""
import numpy as np
from scipy import stats

ALPHA = 0.05
MIN_PER_GROUP = 3


def _insufficient(question, counts):
    return {"question": question, "status": "insufficient_data", "group_sizes": counts}


def compare_two_groups(a, b, question, labels=("group A", "group B")):
    """Welch's t-test, or Mann-Whitney U when either group fails a normality check."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    counts = {labels[0]: int(len(a)), labels[1]: int(len(b))}
    if len(a) < MIN_PER_GROUP or len(b) < MIN_PER_GROUP:
        return _insufficient(question, counts)

    if np.ptp(np.concatenate([a, b])) == 0:
        return {"question": question, "status": "no_variation", "group_sizes": counts}

    # Shapiro-Wilk needs at least 3 values and some spread; with small samples it has
    # little power, which is stated in the report.
    normal = (
        a.std() > 0 and b.std() > 0
        and stats.shapiro(a).pvalue > ALPHA and stats.shapiro(b).pvalue > ALPHA
    )
    if normal:
        result = stats.ttest_ind(a, b, equal_var=False)
        test = "Welch t-test"
    else:
        result = stats.mannwhitneyu(a, b, alternative="two-sided")
        test = "Mann-Whitney U"

    return {
        "question": question,
        "status": "ok",
        "test": test,
        "group_sizes": counts,
        "means": {labels[0]: round(float(a.mean()), 3), labels[1]: round(float(b.mean()), 3)},
        "medians": {labels[0]: round(float(np.median(a)), 3), labels[1]: round(float(np.median(b)), 3)},
        "statistic": round(float(result.statistic), 4),
        "p_value": round(float(result.pvalue), 4),
        "significant": bool(result.pvalue < ALPHA),
    }


def lead_time_by_material(orders):
    """H1: orders whose material was not in stock take longer."""
    done = orders[orders["completed"]]
    return compare_two_groups(
        done.loc[~done["material_in_stock"], "lead_days"],
        done.loc[done["material_in_stock"], "lead_days"],
        "Lead time (days): material not in stock vs in stock",
        labels=("not in stock", "in stock"),
    )


def defect_rate_by_box_type(orders):
    """Does the order-level defect rate differ between box types? (Kruskal-Wallis)

    The order is the unit of observation, so stages of the same order are not
    counted as independent observations.
    """
    data = orders.dropna(subset=["defect_rate"])
    groups = {name: g["defect_rate"].to_numpy() for name, g in data.groupby("box_type")}
    counts = {name: int(len(v)) for name, v in groups.items()}
    usable = {name: v for name, v in groups.items() if len(v) >= MIN_PER_GROUP}
    question = "Order defect rate by box type"
    if len(usable) < 2:
        return _insufficient(question, counts)
    result = stats.kruskal(*usable.values())
    return {
        "question": question,
        "status": "ok",
        "test": "Kruskal-Wallis",
        "group_sizes": counts,
        "groups_tested": sorted(usable),
        "mean_defect_rate_pct": {k: round(100 * float(v.mean()), 2) for k, v in usable.items()},
        "statistic": round(float(result.statistic), 4),
        "p_value": round(float(result.pvalue), 4),
        "significant": bool(result.pvalue < ALPHA),
    }


def duration_by_operators(stages):
    """Within the same stage, is the duration different with 1 vs 2 operators?"""
    data = stages[stages["duration_plausible"] & stages["operators"].notna()]
    results = []
    for stage, g in data.groupby("stage"):
        results.append(compare_two_groups(
            g.loc[g["operators"] == 1, "duration_hours"],
            g.loc[g["operators"] == 2, "duration_hours"],
            f"Stage duration (hours), 1 vs 2 operators: {stage}",
            labels=("1 operator", "2 operators"),
        ))
    return results


def quantity_vs_lead_time(orders):
    """Pearson correlation between order quantity and lead time."""
    done = orders[orders["completed"]].dropna(subset=["lead_days"])
    question = "Pearson correlation: order quantity vs lead time"
    if len(done) < 5:
        return _insufficient(question, {"orders": int(len(done))})
    r, p = stats.pearsonr(done["quantity"], done["lead_days"])
    return {
        "question": question,
        "status": "ok",
        "test": "Pearson r",
        "group_sizes": {"orders": int(len(done))},
        "r": round(float(r), 3),
        "p_value": round(float(p), 4),
        "significant": bool(p < ALPHA),
    }


def material_wait_vs_lead_time(orders):
    """Pearson correlation between days waiting for material and lead time."""
    done = orders[orders["completed"]].dropna(subset=["lead_days", "material_wait_days"])
    question = "Pearson correlation: days waiting for material vs lead time"
    if len(done) < 5:
        return _insufficient(question, {"orders": int(len(done))})
    r, p = stats.pearsonr(done["material_wait_days"], done["lead_days"])
    return {
        "question": question,
        "status": "ok",
        "test": "Pearson r",
        "group_sizes": {"orders": int(len(done))},
        "mean_wait_days": round(float(done["material_wait_days"].mean()), 2),
        "r": round(float(r), 3),
        "p_value": round(float(p), 4),
        "significant": bool(p < ALPHA),
    }


def run_all(orders, stages):
    return {
        "material_wait_vs_lead_time": material_wait_vs_lead_time(orders),
        "lead_time_by_material": lead_time_by_material(orders),
        "defect_rate_by_box_type": defect_rate_by_box_type(orders),
        "duration_by_operators": duration_by_operators(stages),
        "quantity_vs_lead_time": quantity_vs_lead_time(orders),
    }
