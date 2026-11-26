"""Tests for the JSON REST API (/api/v1)."""

NEW_ORDER = {
    "order_code": "API-1",
    "box_type": "PLAIN",
    "quantity": 1000,
    "received_at": "2026-10-20T09:00",
    "material_in_stock": True,
}


def test_api_requires_login(anon_client):
    response = anon_client.get("/api/v1/orders")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Login required."


def test_create_and_read_order(client):
    response = client.post("/api/v1/orders", json=NEW_ORDER)
    assert response.status_code == 201
    created = response.get_json()
    assert response.headers["Location"] == f"/api/v1/orders/{created['id']}"
    assert [s["code"] for s in created["stages"]] == ["CORRUGATE", "MOUNT", "PRESS", "DIECUT", "GLUING"]

    listing = client.get("/api/v1/orders?status=open").get_json()
    assert [o["order_code"] for o in listing["orders"]] == ["API-1"]


def test_invalid_order_returns_422_with_field_errors(client):
    response = client.post("/api/v1/orders", json={**NEW_ORDER, "quantity": -5})
    assert response.status_code == 422
    assert "quantity" in response.get_json()["errors"]


def test_duplicate_order_returns_409(client):
    client.post("/api/v1/orders", json=NEW_ORDER)
    response = client.post("/api/v1/orders", json={**NEW_ORDER, "order_code": "api-1"})
    assert response.status_code == 409


def test_update_order(client):
    order_id = client.post("/api/v1/orders", json=NEW_ORDER).get_json()["id"]
    response = client.put(f"/api/v1/orders/{order_id}", json={**NEW_ORDER, "quantity": 2000})
    assert response.status_code == 200
    assert response.get_json()["quantity"] == 2000


def test_start_and_finish_stage_through_api(client):
    order = client.post("/api/v1/orders", json=NEW_ORDER).get_json()
    stage_id = order["stages"][0]["stage_id"]
    url = f"/api/v1/orders/{order['id']}/stages/{stage_id}"

    started = client.post(f"{url}/start", json={"started_at": "2026-10-21T09:00"})
    assert started.status_code == 201
    assert client.post(f"{url}/start", json={}).status_code == 409  # only once

    finished = client.post(f"{url}/finish", json={
        "boxes_completed": 1000, "boxes_defective": 4, "finished_at": "2026-10-21T10:30",
    })
    stage = finished.get_json()["stages"][0]
    assert stage["status"] == "finished"
    assert stage["machine"] == "M01"
    assert stage["boxes_defective"] == 4


def test_only_owner_can_delete_through_api(client, owner_client):
    order_id = client.post("/api/v1/orders", json=NEW_ORDER).get_json()["id"]
    assert client.delete(f"/api/v1/orders/{order_id}").status_code == 403
    assert owner_client.delete(f"/api/v1/orders/{order_id}").status_code == 204
    assert client.get(f"/api/v1/orders/{order_id}").status_code == 404


def test_api_write_needs_csrf_header(flask_app, client):
    flask_app.config["CSRF_ENABLED"] = True
    assert client.post("/api/v1/orders", json=NEW_ORDER).status_code == 400

    token = client.get("/api/v1/session").get_json()["csrf_token"]
    response = client.post("/api/v1/orders", json=NEW_ORDER, headers={"X-CSRF-Token": token})
    assert response.status_code == 201
