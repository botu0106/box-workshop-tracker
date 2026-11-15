"""Integration tests: forms -> validation -> PostgreSQL -> pages."""
import psycopg2
import pytest

VALID_ORDER = {
    "order_code": "T-100",
    "box_type_id": "1",
    "quantity": "1000",
    "received_at": "2026-10-20T09:00",
    "promised_date": "2026-10-27",
    "material_in_stock": "yes",
}


def test_health_reports_reference_data(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "box_types": 4}


def test_valid_order_is_saved_with_provenance(client, db_cursor):
    response = client.post("/orders/new", data=VALID_ORDER, follow_redirects=True)
    assert response.status_code == 200
    assert "T-100" in response.get_data(as_text=True)  # visible on the order page

    db_cursor.execute("SELECT * FROM orders WHERE order_code = 'T-100';")
    row = db_cursor.fetchone()
    assert row is not None
    assert row["entered_by"] == "manager"
    assert row["source"] == "web_form"
    assert row["created_at"] is not None
    assert row["open_orders_at_receipt"] == 0


def test_order_without_received_time_is_rejected(client, db_cursor):
    response = client.post("/orders/new", data={**VALID_ORDER, "received_at": ""})
    assert "qabul qilingan vaqtni kiriting" in response.get_data(as_text=True)

    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 0


def test_invalid_order_is_not_saved(client, db_cursor):
    response = client.post("/orders/new", data={**VALID_ORDER, "quantity": "-1"})
    assert response.status_code == 200
    assert "Soni musbat butun son" in response.get_data(as_text=True)

    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 0


def test_duplicate_order_code_is_rejected_case_insensitively(client, db_cursor):
    client.post("/orders/new", data={**VALID_ORDER, "order_code": "t-200"})
    response = client.post("/orders/new", data={**VALID_ORDER, "order_code": "T-200"})
    assert "allaqachon mavjud" in response.get_data(as_text=True)

    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 1


def test_database_rejects_machine_not_allowed_for_stage(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO orders (order_code, box_type_id, quantity, received_at,
                            material_in_stock, open_orders_at_receipt, entered_by)
        VALUES ('T-300', 1, 1000, '2026-10-20 09:00', true, 0, 'test')
        RETURNING order_id;
        """
    )
    order_id = db_cursor.fetchone()["order_id"]

    # Manual gluing on the corrugating machine must be blocked by the database itself
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        db_cursor.execute(
            """
            INSERT INTO stage_events (order_id, stage_id, machine_id, started_at, entered_by)
            VALUES (%s,
                    (SELECT stage_id FROM stages WHERE code = 'GLUING'),
                    (SELECT machine_id FROM machines WHERE code = 'M01'),
                    '2026-10-21 09:00', 'test');
            """,
            (order_id,),
        )
