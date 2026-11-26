"""Tests for the owner dashboard and the lead-time estimate."""
from analysis import data, forecast
from analysis.synthetic import make_tables
from tests.test_flow import _create_order, _finish, _stage_id, _start

PLAIN_ROUTE = ["CORRUGATE", "MOUNT", "PRESS", "DIECUT", "GLUING"]


def _complete_order(client, cur, code):
    order = _create_order(client, cur, code=code)
    for hour, stage_code in enumerate(PLAIN_ROUTE, start=9):
        stage_id = _stage_id(cur, stage_code)
        _start(client, order["order_id"], stage_id, started_at=f"2026-10-21T{hour:02d}:00")
        _finish(client, order["order_id"], stage_id, finished_at=f"2026-10-21T{hour:02d}:45",
                boxes_defective="10")
    return order


def test_dashboard_works_with_no_data(client):
    page = client.get("/dashboard").get_data(as_text=True)
    assert "Hisobot" in page
    assert "Hali tugagan bosqichlar yoʻq" in page


def test_new_record_updates_the_dashboard(client, db_cursor):
    before = client.get("/dashboard").get_data(as_text=True)
    assert "Gofrokarton kesish" not in before

    _complete_order(client, db_cursor, "D-1")
    after = client.get("/dashboard").get_data(as_text=True)
    assert "Gofrokarton kesish" in after   # stage duration chart now has data
    assert "Oddiy quti" in after           # defect chart by box type
    # 5 stages x 10 defective boxes = 50 of 1000 ordered -> 5% for this order
    assert "5.0<span" in after
    # received 20 Oct 09:00, last stage finished 21 Oct 13:45 -> 1.2 days
    assert "1.2 <span" in after


def test_open_orders_with_and_without_promised_date(client, db_cursor):
    _create_order(client, db_cursor, code="NO-DATE")  # no promised date: must not break the page
    db_cursor.execute("SELECT box_type_id FROM box_types WHERE code = 'PLAIN';")
    client.post("/orders/new", data={
        "order_code": "LATE", "box_type_id": str(db_cursor.fetchone()["box_type_id"]),
        "quantity": "1000", "received_at": "2026-10-20T09:00", "promised_date": "2026-10-22",
        "material_in_stock": "no",
    })
    page = client.get("/dashboard")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert html.count("vaʼda:") == 1                   # only the order with a passed promise date
    assert "vaʼda: 22.10" in html
    assert "Xomashyo kutayotgan buyurtmalar" in html   # LATE has no material yet


def test_estimate_falls_back_to_median_with_few_orders(client, db_cursor):
    _complete_order(client, db_cursor, "D-1")
    page = client.get("/dashboard?box_code=PLAIN&quantity=1000&material=yes").get_data(as_text=True)
    assert "Model uchun kamida" in page


def test_estimate_uses_a_model_with_enough_orders():
    tables = make_tables(60)
    stages = data.build_stages(tables)
    orders = data.build_orders(tables, stages)
    result = forecast.predict_lead_time(orders, {
        "box_code": "OFFSET", "finishing": "none", "quantity": 1500,
        "material_in_stock": False, "open_orders_at_receipt": 3,
    })
    assert result["status"] == "ok"
    assert result["days"] > 0
    assert result["method"] in ("baseline (median by box type)", "linear regression", "random forest")


def test_invalid_estimate_input_shows_a_message(client):
    page = client.get("/dashboard?box_code=NOPE&quantity=abc").get_data(as_text=True)
    assert "toʻgʻri kiriting" in page


def test_trend_charts_show_recent_orders(client, db_cursor):
    from datetime import timedelta
    from app.validation import WORKSHOP_TZ, local_now

    received = local_now() - timedelta(days=2)
    order = _create_order(client, db_cursor, code="TREND")
    aware = received.replace(tzinfo=WORKSHOP_TZ)  # the test connection is not in workshop time
    db_cursor.execute("UPDATE orders SET received_at = %s WHERE order_id = %s;", (aware, order["order_id"]))
    db_cursor.connection.commit()  # release the row lock before the app updates the order
    for hours, stage_code in enumerate(PLAIN_ROUTE, start=1):
        stage_id = _stage_id(db_cursor, stage_code)
        start = received + timedelta(hours=hours)
        _start(client, order["order_id"], stage_id, started_at=start.strftime("%Y-%m-%dT%H:%M"))
        _finish(client, order["order_id"], stage_id,
                finished_at=(start + timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M"))

    html = client.get("/dashboard").get_data(as_text=True)
    assert html.count("<svg viewBox") == 4  # 3 trends + weekly production
    assert f"{received:%d.%m}: 1 ta qabul qilindi" in html
    assert "№ TREND" in html  # tooltip on the lead-time point


def test_production_counts_good_boxes_by_month(client, db_cursor):
    """A completed order adds (quantity - defective) boxes to the month it was completed."""
    from app.dashboard import MONTHS
    from app.validation import WORKSHOP_TZ, local_now

    order = _complete_order(client, db_cursor, "P-1")
    now = local_now()
    # Move the completion to today so the test does not depend on the calendar
    db_cursor.execute("UPDATE orders SET completed_at = %s WHERE order_id = %s;",
                      (now.replace(tzinfo=WORKSHOP_TZ), order["order_id"]))
    db_cursor.connection.commit()

    html = client.get("/dashboard").get_data(as_text=True)
    assert "Ishlab chiqarish hajmi" in html
    assert f"{MONTHS[now.month - 1]} {now.year}" in html
    # 1000 ordered - 5 stages x 10 defective = 950 good boxes
    assert '950 <span class="fs-6 fw-normal">dona</span>' in html
    assert "950 ta sifatli quti" in html
