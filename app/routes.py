from datetime import datetime

import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from .db import get_db
from .validation import validate_order, validate_stage_event

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

def get_open_orders():
    cur = get_db().cursor()
    cur.execute(
        "SELECT order_id, order_code, received_at FROM orders "
        "WHERE completed_at IS NULL ORDER BY received_at DESC;"
    )
    return cur.fetchall()


def get_stages():
    cur = get_db().cursor()
    cur.execute("SELECT stage_id, code, name FROM stages ORDER BY stage_id;")
    return cur.fetchall()


def get_machines():
    cur = get_db().cursor()
    cur.execute(
        "SELECT machine_id, code, machine_type FROM machines WHERE active ORDER BY code;"
    )
    return cur.fetchall()


@bp.route("/stages/new", methods=["GET", "POST"])
def new_stage_event():
    orders = get_open_orders()
    stages = get_stages()
    machines = get_machines()
    errors = {}
    form = request.args  # allows ?order_id=5 to pre-select an order
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")

    if request.method == "POST":
        form = request.form
        # DB returns timezone-aware times; drop tzinfo to compare with form input
        order_map = {o["order_id"]: o["received_at"].replace(tzinfo=None) for o in orders}
        data, errors = validate_stage_event(
            form,
            order_map,
            {s["stage_id"] for s in stages},
            {m["machine_id"] for m in machines},
        )

        if not errors:
            conn = get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO stage_events (
                            order_id, stage_id, machine_id, started_at, finished_at,
                            operators, boxes_completed, boxes_defective,
                            entry_mode, entered_by, source
                        )
                        VALUES (
                            %(order_id)s, %(stage_id)s, %(machine_id)s,
                            %(started_at)s, %(finished_at)s, %(operators)s,
                            %(boxes_completed)s, %(boxes_defective)s,
                            %(entry_mode)s, %(entered_by)s, 'web_form'
                        )
                        RETURNING stage_event_id;
                        """,
                        data,
                    )
                    new_id = cur.fetchone()["stage_event_id"]
                conn.commit()
                flash(f"Stage saved (ID {new_id}).", "success")
                return redirect(url_for("main.order_detail", order_id=data["order_id"]))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash("The database rejected this record. Please check the values.", "danger")

    return render_template(
        "stage_form.html",
        orders=orders, stages=stages, machines=machines,
        errors=errors, form=form, now_str=now_str,
    )


@bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT o.*, b.name AS box_type
        FROM orders o JOIN box_types b USING (box_type_id)
        WHERE o.order_id = %s;
        """,
        (order_id,),
    )
    order = cur.fetchone()
    if order is None:
        abort(404)

    cur.execute(
        """
        SELECT se.*, s.name AS stage_name, m.code AS machine_code
        FROM stage_events se
        JOIN stages s USING (stage_id)
        LEFT JOIN machines m USING (machine_id)
        WHERE se.order_id = %s
        ORDER BY se.started_at;
        """,
        (order_id,),
    )
    return render_template("order_detail.html", order=order, stages=cur.fetchall())