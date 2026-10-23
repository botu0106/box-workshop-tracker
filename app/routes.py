import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash

from .db import get_db
from .validation import validate_order

bp = Blueprint("main", __name__)


@bp.route("/health")
def health():
    cur = get_db().cursor()
    cur.execute("SELECT COUNT(*) AS n FROM box_types;")
    n = cur.fetchone()["n"]
    return {"status": "ok", "box_types": n}


def get_box_types():
    cur = get_db().cursor()
    cur.execute("SELECT box_type_id, code, name FROM box_types ORDER BY box_type_id;")
    return cur.fetchall()


@bp.route("/orders/new", methods=["GET", "POST"])
def new_order():
    box_types = get_box_types()
    errors, form = {}, {}

    if request.method == "POST":
        form = request.form
        valid_ids = {b["box_type_id"] for b in box_types}
        data, errors = validate_order(form, valid_ids)

        if not errors:
            conn = get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO orders (
                            order_code, box_type_id, quantity, received_at,
                            promised_date, material_in_stock,
                            open_orders_at_receipt, entered_by, source
                        )
                        VALUES (
                            %(order_code)s, %(box_type_id)s, %(quantity)s, %(received_at)s,
                            %(promised_date)s, %(material_in_stock)s,
                            (SELECT COUNT(*) FROM orders
                             WHERE received_at <= %(received_at)s
                               AND (completed_at IS NULL OR completed_at > %(received_at)s)),
                            %(entered_by)s, 'web_form'
                        )
                        RETURNING order_id;
                        """,
                        data,
                    )
                    new_id = cur.fetchone()["order_id"]
                conn.commit()
                flash(f"Order {data['order_code']} saved (ID {new_id}).", "success")
                return redirect(url_for("main.list_orders"))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                errors["order_code"] = "An order with this code already exists."

    return render_template("order_form.html", box_types=box_types, errors=errors, form=form)


@bp.route("/orders")
def list_orders():
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT o.order_id, o.order_code, b.name AS box_type, o.quantity,
               o.received_at, o.promised_date, o.material_in_stock,
               o.open_orders_at_receipt, o.entered_by, o.source, o.created_at
        FROM orders o
        JOIN box_types b ON b.box_type_id = o.box_type_id
        ORDER BY o.created_at DESC;
        """
    )
    return render_template("orders.html", orders=cur.fetchall())