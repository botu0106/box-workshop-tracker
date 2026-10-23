import psycopg2
import psycopg2.extras
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            **current_app.config["DB"],
            cursor_factory=psycopg2.extras.RealDictCursor,
            options="-c timezone=Asia/Tashkent",
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)