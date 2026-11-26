import functools
import time
from collections import defaultdict, deque

import psycopg2
from flask import (
    Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request,
    session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

# Login throttling: at most LOGIN_LIMIT failed attempts per address in LOGIN_WINDOW seconds.
# Kept in memory, which fits the single server process the app runs as.
LOGIN_LIMIT = 5
LOGIN_WINDOW = 10 * 60
_failed_logins = defaultdict(deque)

MIN_PASSWORD_LENGTH = 8


@bp.before_app_request
def load_logged_in_user():
    """Load the logged-in user (if any) before every request."""
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        cur = get_db().cursor()
        cur.execute(
            "SELECT user_id, username, role FROM users WHERE user_id = %s AND active;",
            (user_id,),
        )
        g.user = cur.fetchone()


def _not_logged_in():
    if request.path.startswith("/api/"):
        return jsonify(error="Login required."), 401
    return redirect(url_for("auth.login", next=request.path))


def login_required(view):
    """Only logged-in users; others go to the login page (or get 401 from the API)."""
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return _not_logged_in()
        return view(**kwargs)
    return wrapped


def owner_required(view):
    """Only the workshop owner (role 'owner'), e.g. for deleting orders and managing users."""
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return _not_logged_in()
        if g.user["role"] != "owner":
            if request.path.startswith("/api/"):
                return jsonify(error="Only the owner can do this."), 403
            abort(403)
        return view(**kwargs)
    return wrapped


def _safe_next(url):
    """Only allow redirects to pages on this site (prevents open redirects)."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return url_for("main.list_orders")


def _too_many_attempts(address):
    attempts = _failed_logins[address]
    while attempts and attempts[0] < time.monotonic() - LOGIN_WINDOW:
        attempts.popleft()
    return len(attempts) >= LOGIN_LIMIT


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        address = request.remote_addr or "unknown"
        if not current_app.config.get("TESTING_NO_THROTTLE") and _too_many_attempts(address):
            return render_template(
                "login.html", error="Juda koʻp urinish. 10 daqiqadan keyin qayta urinib koʻring.",
            ), 429

        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        cur = get_db().cursor()
        cur.execute(
            "SELECT user_id, password_hash, active FROM users WHERE username = %s;",
            (username,),
        )
        user = cur.fetchone()

        # Same message for unknown user and wrong password, so usernames cannot be guessed
        if user is None or not check_password_hash(user["password_hash"], password):
            _failed_logins[address].append(time.monotonic())
            error = "Login yoki parol notoʻgʻri."
        elif not user["active"]:
            error = "Hisobingiz hali egasi tomonidan tasdiqlanmagan."
        else:
            _failed_logins.pop(address, None)
            session.clear()
            session["user_id"] = user["user_id"]
            return redirect(_safe_next(request.args.get("next")))

    return render_template("login.html", error=error)


def validate_registration(form):
    errors = {}
    username = (form.get("username") or "").strip().lower()
    if not (3 <= len(username) <= 30) or not username.replace("_", "").isalnum():
        errors["username"] = "Login 3–30 ta harf, raqam yoki _ dan iborat boʻlishi kerak."
    password = form.get("password") or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = f"Parol kamida {MIN_PASSWORD_LENGTH} ta belgidan iborat boʻlishi kerak."
    elif password != (form.get("password_confirm") or ""):
        errors["password_confirm"] = "Parollar bir xil emas."
    return username, password, errors


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Anyone can ask for an account; it stays inactive until the owner approves it."""
    errors, form = {}, {}
    if request.method == "POST":
        form = request.form
        username, password, errors = validate_registration(form)
        if not errors:
            conn = get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (username, password_hash, role, active)
                        VALUES (%s, %s, 'manager', FALSE);
                        """,
                        (username, generate_password_hash(password)),
                    )
                conn.commit()
                flash("Soʻrov yuborildi. Egasi tasdiqlagach, tizimga kira olasiz.", "success")
                return redirect(url_for("auth.login"))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                errors["username"] = "Bu login band."
    return render_template("register.html", errors=errors, form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Tizimdan chiqdingiz.", "success")
    return redirect(url_for("auth.login"))


# ---------- User management (owner only) ----------

@bp.route("/users")
@owner_required
def list_users():
    cur = get_db().cursor()
    cur.execute(
        "SELECT user_id, username, role, active, created_at FROM users ORDER BY active, username;"
    )
    return render_template("users.html", users=cur.fetchall())


@bp.route("/users/<int:user_id>", methods=["POST"])
@owner_required
def update_user(user_id):
    """Approve or block an account, or change its role. The owner cannot lock themselves out."""
    if user_id == g.user["user_id"]:
        flash("Oʻz hisobingizni bu yerda oʻzgartira olmaysiz.", "warning")
        return redirect(url_for("auth.list_users"))

    action = request.form.get("action")
    changes = {
        "approve": "active = TRUE",
        "block": "active = FALSE",
        "make_owner": "role = 'owner'",
        "make_manager": "role = 'manager'",
    }
    if action not in changes:
        abort(400)
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(f"UPDATE users SET {changes[action]} WHERE user_id = %s RETURNING user_id;", (user_id,))
        if cur.fetchone() is None:
            abort(404)
    conn.commit()
    flash("Foydalanuvchi yangilandi.", "success")
    return redirect(url_for("auth.list_users"))
