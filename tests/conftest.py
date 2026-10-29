"""Shared pytest fixtures.

Tests use a separate database (workshop_test) that is rebuilt from
db/schema.sql and db/reference_data.sql before every test, so the real
collected data is never touched. All records created in tests are
synthetic test fixtures.
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from app import create_app

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
TEST_DB = "workshop_test"
TEST_USER = "manager"
TEST_PASSWORD = "test-password"


def _db_settings(dbname):
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5433"),
        "dbname": dbname,
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


@pytest.fixture(scope="session")
def test_db():
    """Create the test database once per test run if it does not exist."""
    admin = psycopg2.connect(**_db_settings(os.getenv("POSTGRES_DB")))
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (TEST_DB,))
        if cur.fetchone() is None:
            cur.execute(f"CREATE DATABASE {TEST_DB};")
    admin.close()
    return _db_settings(TEST_DB)


@pytest.fixture()
def flask_app(test_db):
    """Rebuild the test schema, add a test user and return an app connected to it."""
    conn = psycopg2.connect(**test_db)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        cur.execute((ROOT / "db" / "reference_data.sql").read_text(encoding="utf-8"))
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'manager');",
            (TEST_USER, generate_password_hash(TEST_PASSWORD)),
        )
    conn.close()

    app = create_app({"TESTING": True, "DB": test_db, "SECRET_KEY": "test"})
    yield app


@pytest.fixture()
def anon_client(flask_app):
    """A client that is not logged in."""
    return flask_app.test_client()


@pytest.fixture()
def client(flask_app):
    """A client that is already logged in as the test user."""
    c = flask_app.test_client()
    response = c.post("/login", data={"username": TEST_USER, "password": TEST_PASSWORD})
    assert response.status_code == 302
    return c


@pytest.fixture()
def db_cursor(flask_app, test_db):
    """A direct database cursor for checking what was saved."""
    conn = psycopg2.connect(**test_db, cursor_factory=psycopg2.extras.RealDictCursor)
    yield conn.cursor()
    conn.close()