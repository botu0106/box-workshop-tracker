"""Request-level protection: CSRF tokens, security headers and error pages."""
import hmac
import secrets

from flask import abort, current_app, jsonify, render_template, request, session

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Bootstrap and its icons load from jsDelivr; everything else must come from this site.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


def csrf_token():
    """The per-session token every form and API write must send back."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf():
    """Reject state-changing requests that do not carry this session's token.

    Forms send it as a hidden field, API clients in the X-CSRF-Token header.
    """
    if request.method not in UNSAFE_METHODS or not current_app.config.get("CSRF_ENABLED", True):
        return None
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(sent, expected):
        if request.path.startswith("/api/"):
            return jsonify(error="Missing or invalid CSRF token."), 400
        abort(400)
    return None


def add_security_headers(response):
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def _error(code, message):
    if request.path.startswith("/api/"):
        return jsonify(error=message), code
    return render_template("error.html", code=code, message=message), code


def init_app(app):
    app.config.setdefault("MAX_CONTENT_LENGTH", 1024 * 1024)  # 1 MB is far more than any form needs
    app.before_request(check_csrf)
    app.after_request(add_security_headers)
    app.jinja_env.globals["csrf_token"] = csrf_token

    app.register_error_handler(400, lambda e: _error(400, "Soʻrov notoʻgʻri. Sahifani yangilab, qayta urinib koʻring."))
    app.register_error_handler(403, lambda e: _error(403, "Bu amal uchun ruxsatingiz yoʻq."))
    app.register_error_handler(404, lambda e: _error(404, "Sahifa topilmadi."))
    app.register_error_handler(413, lambda e: _error(413, "Soʻrov juda katta."))
    app.register_error_handler(500, lambda e: _error(500, "Serverda xatolik yuz berdi."))
