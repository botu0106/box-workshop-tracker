"""Tests for registration, roles, CSRF protection, login throttling and security headers."""
import re

from tests.conftest import TEST_PASSWORD, TEST_USER
from tests.test_flow import _create_order


def test_registration_creates_an_inactive_account(anon_client, db_cursor):
    anon_client.post("/register", data={
        "username": "new_manager", "password": "long-password", "password_confirm": "long-password",
    })
    db_cursor.execute("SELECT active, role FROM users WHERE username = 'new_manager';")
    user = db_cursor.fetchone()
    assert user["active"] is False
    assert user["role"] == "manager"

    response = anon_client.post("/login", data={"username": "new_manager", "password": "long-password"})
    assert "tasdiqlanmagan" in response.get_data(as_text=True)


def test_registration_rejects_short_password(anon_client, db_cursor):
    anon_client.post("/register", data={
        "username": "shorty", "password": "123", "password_confirm": "123",
    })
    db_cursor.execute("SELECT COUNT(*) AS n FROM users WHERE username = 'shorty';")
    assert db_cursor.fetchone()["n"] == 0


def test_owner_can_approve_a_registered_user(owner_client, anon_client, db_cursor):
    anon_client.post("/register", data={
        "username": "worker", "password": "long-password", "password_confirm": "long-password",
    })
    db_cursor.execute("SELECT user_id FROM users WHERE username = 'worker';")
    user_id = db_cursor.fetchone()["user_id"]

    owner_client.post(f"/users/{user_id}", data={"action": "approve"})
    response = anon_client.post("/login", data={"username": "worker", "password": "long-password"})
    assert response.status_code == 302


def test_manager_cannot_manage_users_or_delete_orders(client, db_cursor):
    order = _create_order(client, db_cursor)
    assert client.get("/users").status_code == 403
    assert client.post(f"/orders/{order['order_id']}/delete").status_code == 403
    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 1


def test_owner_can_delete_an_order_with_its_stages(owner_client, client, db_cursor):
    order = _create_order(client, db_cursor)
    db_cursor.execute("SELECT stage_id FROM stages WHERE code = 'CORRUGATE';")
    client.post(f"/orders/{order['order_id']}/stages/{db_cursor.fetchone()['stage_id']}/start",
                data={"started_at": "2026-10-21T09:00"})

    owner_client.post(f"/orders/{order['order_id']}/delete")
    db_cursor.execute("SELECT (SELECT COUNT(*) FROM orders) AS o, (SELECT COUNT(*) FROM stage_events) AS s;")
    counts = db_cursor.fetchone()
    assert counts["o"] == 0 and counts["s"] == 0


def test_form_without_csrf_token_is_rejected(flask_app, client, db_cursor):
    flask_app.config["CSRF_ENABLED"] = True
    response = client.post("/orders/new", data={
        "order_code": "X-1", "box_type_id": "1", "quantity": "1000",
        "received_at": "2026-10-20T09:00", "material_in_stock": "yes",
    })
    assert response.status_code == 400
    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 0


def test_form_with_csrf_token_is_accepted(flask_app, client, db_cursor):
    flask_app.config["CSRF_ENABLED"] = True
    page = client.get("/orders/new").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    client.post("/orders/new", data={
        "csrf_token": token, "order_code": "X-1", "box_type_id": "1", "quantity": "1000",
        "received_at": "2026-10-20T09:00", "material_in_stock": "yes",
    })
    db_cursor.execute("SELECT COUNT(*) AS n FROM orders;")
    assert db_cursor.fetchone()["n"] == 1


def test_repeated_failed_logins_are_throttled(flask_app, anon_client):
    flask_app.config["TESTING_NO_THROTTLE"] = False
    for _ in range(5):
        anon_client.post("/login", data={"username": TEST_USER, "password": "wrong"})
    response = anon_client.post("/login", data={"username": TEST_USER, "password": TEST_PASSWORD})
    assert response.status_code == 429


def test_security_headers_are_sent(anon_client):
    headers = anon_client.get("/login").headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_unknown_page_returns_404(client):
    assert client.get("/no-such-page").status_code == 404
