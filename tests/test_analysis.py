"""Tests for the analysis package. All data here is synthetic test data."""
import pandas as pd
import psycopg2.extras

from analysis import data, models, stats
from analysis.run import analyse
from analysis.synthetic import make_tables
from tests.test_flow import _create_order, _finish, _stage_id, _start


def _datasets(n_orders=60):
    tables = make_tables(n_orders)
    stages = data.build_stages(tables)
    return data.build_orders(tables, stages), stages


def test_lead_time_and_defect_rate_are_per_order():
    orders, stages = _datasets(10)
    first = orders.iloc[0]
    expected_days = (first["completed_at"] - first["received_at"]).total_seconds() / 86400
    assert abs(first["lead_days"] - expected_days) < 1e-9

    own = stages[stages["order_id"] == first["order_id"]]
    assert first["defect_rate"] == own["boxes_defective"].sum() / first["quantity"]


def test_chronological_split_uses_only_outcomes_known_before_the_test_period():
    orders, _ = _datasets(60)
    train, test, cutoff = models.chronological_split(orders)
    assert (train["completed_at"] < cutoff).all()
    assert (test["received_at"] >= cutoff).all()
    assert set(train["order_id"]).isdisjoint(test["order_id"])


def test_models_report_insufficient_data_instead_of_numbers():
    orders, _ = _datasets(5)
    result = models.evaluate(orders)
    assert result["status"] == "insufficient_data"
    assert "results" not in result


def test_baseline_predicts_median_of_the_box_type():
    X = pd.DataFrame({"box_code": ["PLAIN", "PLAIN", "PLAIN", "MICRO"]})
    baseline = models.MedianByBoxType().fit(X, [1.0, 2.0, 9.0, 4.0])
    unseen = pd.DataFrame({"box_code": ["PLAIN", "STENCIL"]})
    assert list(baseline.predict(unseen)) == [2.0, 3.0]  # STENCIL falls back to overall median


def test_two_group_test_needs_enough_observations():
    result = stats.compare_two_groups([1.0, 2.0], [3.0, 4.0, 5.0], "small sample")
    assert result["status"] == "insufficient_data"


def test_full_analysis_writes_report_and_figures(tmp_path):
    results = analyse(make_tables(60), tmp_path, synthetic=True)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in report
    assert results["prediction"]["status"] == "ok"
    assert len(results["figures"]) >= 5
    assert (tmp_path / "results.json").exists()


def test_analysis_reads_records_from_the_database(client, db_cursor, test_db):
    order = _create_order(client, db_cursor)
    cutting = _stage_id(db_cursor, "CORRUGATE")
    _start(client, order["order_id"], cutting)
    _finish(client, order["order_id"], cutting, boxes_defective="7")

    conn = psycopg2.connect(**test_db, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        tables = data.load_tables(conn)
    finally:
        conn.close()
    stages = data.build_stages(tables)
    orders = data.build_orders(tables, stages)
    assert len(orders) == 1
    assert orders.iloc[0]["boxes_defective"] == 7
    assert stages.iloc[0]["duration_hours"] == 1.0
