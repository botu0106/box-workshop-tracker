"""Tests for login, access control and password storage."""
from werkzeug.security import check_password_hash

from tests.conftest import TEST_PASSWORD, TEST_USER

ORDER = {
    "order_code": "A-1",
    "box_type_id": "1",
    "quantity": "1000",
    "received_at": "2026-10-20T09:00",
    "material_in_stock": "yes",
}


def test_data_pages_require_login(anon_client):
    response = anon_client.get("/orders")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_health_check_stays_public(anon_client):
    assert anon_client.get("/health").status_code == 200


def test_wrong_password_is_rejected(anon_client):
    response = anon_client.post("/login", data={"username": TEST_USER, "password": "wrong"})
    assert response.status_code == 200
    assert b"Incorrect username or password." in response.data
    assert anon_client.get("/orders").status_code == 302  # still not logged in


def test_password_is_stored_only_as_hash(db_cursor):
    db_cursor.execute("SELECT password_hash FROM users WHERE username = %s;", (TEST_USER,))
    stored = db_cursor.fetchone()["password_hash"]
    assert stored != TEST_PASSWORD
    assert check_password_hash(stored, TEST_PASSWORD)


def test_entered_by_comes_from_logged_in_user(client, db_cursor):
    # Even if someone sends a different name, the logged-in user is recorded
    client.post("/orders/new", data={**ORDER, "entered_by": "someone_else"})
    db_cursor.execute("SELECT entered_by FROM orders WHERE order_code = 'A-1';")
    assert db_cursor.fetchone()["entered_by"] == TEST_USER


def test_logout_ends_the_session(client):
    client.post("/logout")
    assert client.get("/orders").status_code == 302