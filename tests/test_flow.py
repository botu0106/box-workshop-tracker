"""Tests for the route checklist: start and finish a stage, automatic order completion."""


def _create_order(client, cur, code="F-1", box_code="PLAIN", finishing="none", quantity="1000"):
    cur.execute("SELECT box_type_id FROM box_types WHERE code = %s;", (box_code,))
    box_type_id = cur.fetchone()["box_type_id"]
    client.post("/orders/new", data={
        "order_code": code,
        "box_type_id": str(box_type_id),
        "quantity": quantity,
        "received_at": "2026-10-20T09:00",
        "material_in_stock": "yes",
        "finishing": finishing,
    })
    cur.execute("SELECT * FROM orders WHERE order_code = %s;", (code,))
    return cur.fetchone()


def _stage_id(cur, code):
    cur.execute("SELECT stage_id FROM stages WHERE code = %s;", (code,))
    return cur.fetchone()["stage_id"]


def _start(client, order_id, stage_id, started_at="2026-10-21T09:00"):
    return client.post(
        f"/orders/{order_id}/stages/{stage_id}/start",
        data={"started_at": started_at},
        follow_redirects=True,
    )


def _finish(client, order_id, stage_id, finished_at="2026-10-21T10:00", **fields):
    data = {"boxes_completed": "1000", "boxes_defective": "0", "finished_at": finished_at}
    data.update(fields)
    return client.post(
        f"/orders/{order_id}/stages/{stage_id}/finish", data=data, follow_redirects=True,
    )


def test_start_and_finish_record_stage_with_provenance(client, db_cursor):
    order = _create_order(client, db_cursor)
    cutting = _stage_id(db_cursor, "CORRUGATE")

    _start(client, order["order_id"], cutting)
    _finish(client, order["order_id"], cutting, boxes_defective="5", operators="2")

    db_cursor.execute(
        """
        SELECT se.*, m.code AS machine_code
        FROM stage_events se LEFT JOIN machines m USING (machine_id)
        WHERE se.order_id = %s;
        """,
        (order["order_id"],),
    )
    stage = db_cursor.fetchone()
    assert stage["machine_code"] == "M01"          # filled in automatically
    assert stage["boxes_completed"] == 1000
    assert stage["boxes_defective"] == 5
    assert stage["operators"] == 2
    assert stage["entered_by"] == "manager"
    assert stage["entry_mode"] == "end_of_day"     # recorded long after it happened


def test_stage_cannot_be_started_twice(client, db_cursor):
    order = _create_order(client, db_cursor)
    cutting = _stage_id(db_cursor, "CORRUGATE")

    _start(client, order["order_id"], cutting)
    response = _start(client, order["order_id"], cutting)

    assert "allaqachon boshlangan" in response.get_data(as_text=True)
    db_cursor.execute("SELECT COUNT(*) AS n FROM stage_events WHERE order_id = %s;", (order["order_id"],))
    assert db_cursor.fetchone()["n"] == 1


def test_finish_rejects_more_boxes_than_ordered(client, db_cursor):
    order = _create_order(client, db_cursor)
    cutting = _stage_id(db_cursor, "CORRUGATE")
    _start(client, order["order_id"], cutting)

    response = _finish(client, order["order_id"], cutting, boxes_completed="1200")

    assert "koʻp boʻlishi mumkin emas" in response.get_data(as_text=True)
    db_cursor.execute("SELECT finished_at FROM stage_events WHERE order_id = %s;", (order["order_id"],))
    assert db_cursor.fetchone()["finished_at"] is None


def test_start_before_order_received_is_rejected(client, db_cursor):
    order = _create_order(client, db_cursor)
    response = _start(client, order["order_id"], _stage_id(db_cursor, "CORRUGATE"),
                      started_at="2026-10-19T09:00")

    assert "qabul qilinishidan oldin" in response.get_data(as_text=True)
    db_cursor.execute("SELECT COUNT(*) AS n FROM stage_events;")
    assert db_cursor.fetchone()["n"] == 0


def test_order_completes_automatically_after_last_stage(client, db_cursor):
    order = _create_order(client, db_cursor)
    route = ["CORRUGATE", "MOUNT", "PRESS", "DIECUT", "GLUING"]

    for hour, code in enumerate(route, start=9):
        stage_id = _stage_id(db_cursor, code)
        _start(client, order["order_id"], stage_id, started_at=f"2026-10-21T{hour:02d}:00")
        _finish(client, order["order_id"], stage_id, finished_at=f"2026-10-21T{hour:02d}:45")

    db_cursor.execute(
        """
        SELECT o.completed_by,
               o.completed_at = (SELECT MAX(finished_at) FROM stage_events
                                 WHERE order_id = o.order_id) AS at_last_finish
        FROM orders o WHERE o.order_id = %s;
        """,
        (order["order_id"],),
    )
    row = db_cursor.fetchone()
    assert row["at_last_finish"] is True
    assert row["completed_by"] == "manager"


def test_route_shows_only_the_chosen_finishing(client, db_cursor):
    order = _create_order(client, db_cursor, box_code="OFFSET", finishing="laminate")
    page = client.get(f"/orders/{order['order_id']}").get_data(as_text=True)

    assert "Laminatsiya" in page
    assert "Laklash" not in page


def test_plain_box_ignores_finishing_choice(client, db_cursor):
    order = _create_order(client, db_cursor, box_code="PLAIN", finishing="lacquer")
    assert order["finishing"] == "none"


def test_order_can_be_edited_and_edit_is_recorded(client, db_cursor):
    order = _create_order(client, db_cursor, code="BRAND NAME")
    client.post(f"/orders/{order['order_id']}/edit", data={
        "order_code": "118",
        "box_type_id": str(order["box_type_id"]),
        "quantity": "1500",
        "received_at": "2026-10-20T08:30",
        "material_in_stock": "no",
    })
    db_cursor.execute("SELECT * FROM orders WHERE order_id = %s;", (order["order_id"],))
    row = db_cursor.fetchone()
    assert row["order_code"] == "118"
    assert row["quantity"] == 1500
    assert row["material_in_stock"] is False
    assert row["updated_by"] == "manager"
    assert row["entered_by"] == "manager"  # original provenance kept


def test_box_type_is_locked_after_a_stage_is_recorded(client, db_cursor):
    order = _create_order(client, db_cursor)
    _start(client, order["order_id"], _stage_id(db_cursor, "CORRUGATE"))
    db_cursor.execute("SELECT box_type_id FROM box_types WHERE code = 'MICRO';")
    micro = db_cursor.fetchone()["box_type_id"]

    client.post(f"/orders/{order['order_id']}/edit", data={
        "order_code": "F-1", "box_type_id": str(micro), "quantity": "1000",
        "received_at": "2026-10-20T09:00", "material_in_stock": "yes",
    })
    db_cursor.execute("SELECT box_type_id FROM orders WHERE order_id = %s;", (order["order_id"],))
    assert db_cursor.fetchone()["box_type_id"] == order["box_type_id"]


def _create_order_without_material(client, cur, code="M-1"):
    cur.execute("SELECT box_type_id FROM box_types WHERE code = 'OFFSET';")
    client.post("/orders/new", data={
        "order_code": code, "box_type_id": str(cur.fetchone()["box_type_id"]),
        "quantity": "1000", "received_at": "2026-10-20T09:00", "material_in_stock": "no",
    })
    cur.execute("SELECT * FROM orders WHERE order_code = %s;", (code,))
    return cur.fetchone()


def test_material_arrival_is_recorded(client, db_cursor):
    order = _create_order_without_material(client, db_cursor)
    client.post(f"/orders/{order['order_id']}/material", data={"material_received_at": "2026-10-22T11:00"})
    db_cursor.execute(
        "SELECT material_received_at - received_at AS wait FROM orders WHERE order_id = %s;",
        (order["order_id"],),
    )
    assert str(db_cursor.fetchone()["wait"]) == "2 days, 2:00:00"


def test_material_arrival_before_receipt_is_rejected(client, db_cursor):
    order = _create_order_without_material(client, db_cursor)
    response = client.post(f"/orders/{order['order_id']}/material",
                           data={"material_received_at": "2026-10-19T11:00"}, follow_redirects=True)
    assert "qabul qilinishidan oldin" in response.get_data(as_text=True)
    db_cursor.execute("SELECT material_received_at FROM orders WHERE order_id = %s;", (order["order_id"],))
    assert db_cursor.fetchone()["material_received_at"] is None


def test_arrival_time_is_ignored_when_material_was_in_stock(client, db_cursor):
    order = _create_order(client, db_cursor)  # material in stock
    client.post(f"/orders/{order['order_id']}/edit", data={
        "order_code": "F-1", "box_type_id": str(order["box_type_id"]), "quantity": "1000",
        "received_at": "2026-10-20T09:00", "material_in_stock": "yes",
        "material_received_at": "2026-10-21T09:00",
    })
    db_cursor.execute("SELECT material_received_at FROM orders WHERE order_id = %s;", (order["order_id"],))
    assert db_cursor.fetchone()["material_received_at"] is None
