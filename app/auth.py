import functools

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)


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


def login_required(view):
    """Redirect to the login page if nobody is logged in."""
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped


def _safe_next(url):
    """Only allow redirects to pages on this site (prevents open redirects)."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return url_for("main.list_orders")


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""

        cur = get_db().cursor()
        cur.execute(
            "SELECT user_id, password_hash FROM users WHERE username = %s AND active;",
            (username,),
        )
        user = cur.fetchone()

        # Same message for unknown user and wrong password, so usernames cannot be guessed
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Incorrect username or password."
        else:
            session.clear()
            session["user_id"] = user["user_id"]
            return redirect(_safe_next(request.args.get("next")))

    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))