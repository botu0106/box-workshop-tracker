import os

import click
from dotenv import load_dotenv
from flask import Flask
from werkzeug.security import generate_password_hash


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-key")
    app.config["SESSION_COOKIE_HTTPONLY"] = True   # JavaScript cannot read the session cookie
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # basic protection against cross-site requests
    app.config["DB"] = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5433"),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }

    if test_config:
        app.config.update(test_config)

    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    from .routes import bp
    app.register_blueprint(bp)

    register_commands(app)
    return app


def register_commands(app):
    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", default="manager", type=click.Choice(["manager", "owner"]))
    @click.password_option()
    def create_user(username, role, password):
        """Create a user who can log in."""
        from .db import get_db

        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                RETURNING user_id;
                """,
                (username.strip().lower(), generate_password_hash(password), role),
            )
            created = cur.fetchone()
        conn.commit()
        if created:
            click.echo(f"User '{username}' created.")
        else:
            click.echo(f"User '{username}' already exists.")