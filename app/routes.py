from flask import Blueprint
from .db import get_db

bp = Blueprint("main", __name__)


@bp.route("/health")
def health():
    cur = get_db().cursor()
    cur.execute("SELECT COUNT(*) AS n FROM box_types;")
    n = cur.fetchone()["n"]
    return {"status": "ok", "box_types": n}