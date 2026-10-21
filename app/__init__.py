import os
from dotenv import load_dotenv
from flask import Flask


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-key")
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

    from .routes import bp
    app.register_blueprint(bp)

    return app