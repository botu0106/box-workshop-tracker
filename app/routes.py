from datetime import timedelta

import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g

from .auth import login_required
from .db import get_db
from .validation import (
    local_now, to_local,
    validate_order, validate_stage_event, validate_stage_start, validate_stage_finish,
    validate_material_arrival,
)

bp = Blueprint("main", __name__)

# Box types that may get lamination or lacquer, and the stage each choice adds
FINISHING_BOX_TYPES = {"OFFSET", "MICRO"}
FINISHING_STAGES = {"laminate": "LAMINATE", "lacquer": "LACQUER"}
FINISHING_LABELS = {"none": "Pardozsiz", "laminate": "Laminatsiya", "lacquer": "Lak"}

# A start or finish recorded this long after it happened counts as a late entry
LATE_ENTRY = timedelta(minutes=15)

ORDER_SELECT = """
    SELECT o.*, b.name AS box_type, b.code AS box_code
    FROM orders o
    JOIN box_types b ON b.box_type_id = o.box_type_id
"""


# ---------- Helpers ----------

def get_box_types():
    cur = get_db().cursor()
    cur.execute("SELECT box_type_id, code, name FROM box_types ORDER BY box_type_id;")
    return cur.fetchall()


def get_machines():
    cur = get_db().cursor()
    cur.execute(
        "SELECT machine_id, code, machine_type FROM machines WHERE active ORDER BY code;"
    )
    return cur.fetchall()


def get_stage_machine_pairs():
    cur = get_db().cursor()
    cur.execute("SELECT stage_id, machine_id FROM stage_machines;")
    return cur.fetchall()


def get_order(order_id):
    cur = get_db().cursor()
    cur.execute(ORDER_SELECT + " WHERE o.order_id = %s;", (order_id,))
    order = cur.fetchone()
    if order is None:
        abort(404)
    return order


def get_route(order):
    """The order's stages in workshop order, each with its recorded event (if any).

    Lamination and lacquering appear only when the client chose them.
    """
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT s.stage_id, s.code, s.name, r.position,
               se.stage_event_id, se.started_at, se.finished_at,
               se.boxes_completed, se.boxes_defective, se.operators,
               m.code AS machine_code
        FROM box_type_routes r
        JOIN stages s ON s.stage_id = r.stage_id
        LEFT JOIN stage_events se ON se.stage_id = r.stage_id AND se.order_id = %s
        LEFT JOIN machines m ON m.machine_id = se.machine_id
        WHERE r.box_type_id = %s
        ORDER BY r.position;
        """,
        (order["order_id"], order["box_type_id"]),
    )
    skipped = {code for choice, code in FINISHING_STAGES.items() if choice != order["finishing"]}
    return [stage for stage in cur.fetchall() if stage["code"] not in skipped]


def find_stage(route, stage_id):
    for stage in route:
        if stage["stage_id"] == stage_id:
            return stage
    abort(404)


def single_machine_for(stage_id):
    """The machine of a stage when exactly one machine can do it, else None."""
    machines = [p["machine_id"] for p in get_stage_machine_pairs() if p["stage_id"] == stage_id]
    return machines[0] if len(machines) == 1 else None


def complete_if_all_finished(conn, order):
    """Mark the order completed when every stage of its route is finished."""
    route = get_route(order)
    if not route or not all(stage["finished_at"] for stage in route):
        return False
    last_finish = max(stage["finished_at"] for stage in route)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orders SET completed_at = %s, completed_by = %s
            WHERE order_id = %s AND completed_at IS NULL;
            """,
            (last_finish, g.user["username"], order["order_id"]),
        )
    conn.commit()
    return True


def to_input_datetime(value):
    """Format a timestamp for an <input type="datetime-local">."""
    return to_local(value).strftime("%Y-%m-%dT%H:%M") if value else ""


def now_input():
    return local_now().strftime("%Y-%m-%dT%H:%M")


def form_with_user():
    """Copy the submitted form and set entered_by to the logged-in user."""
    form = request.form.to_dict()
    form["entered_by"] = g.user["username"]
    return form


# ---------- Basic pages ----------

@bp.route("/health")
def health():
    cur = get_db().cursor()
    cur.execute("SELECT COUNT(*) AS n FROM box_types;")
    n = cur.fetchone()["n"]
    return {"status": "ok", "box_types": n}


@bp.route("/")
def index():
    return redirect(url_for("main.list_orders"))


# ---------- Orders ----------

@bp.route("/orders")
@login_required
def list_orders():
    cur = get_db().cursor()
    cur.execute(ORDER_SELECT + " WHERE o.completed_at IS NULL ORDER BY o.received_at;")
    open_rows = cur.fetchall()
    cur.execute(
        ORDER_SELECT
        + " WHERE o.completed_at >= now() - INTERVAL '3 days' ORDER BY o.completed_at DESC;"
    )
    recent = cur.fetchall()

    open_orders = []
    for order in open_rows:
        route = get_route(order)
        done = sum(1 for stage in route if stage["finished_at"])
        open_orders.append({
            **order,
            "total": len(route),
            "done": done,
            "percent": round(100 * done / len(route)) if route else 0,
            "running": [s["name"] for s in route if s["started_at"] and not s["finished_at"]],
            "next_up": next((s["name"] for s in route if not s["started_at"]), None),
        })

    return render_template("orders.html", open_orders=open_orders, recent=recent)


@bp.route("/orders/new", methods=["GET", "POST"])
@login_required
def new_order():
    box_types = get_box_types()
    finishing_ids = {b["box_type_id"] for b in box_types if b["code"] in FINISHING_BOX_TYPES}
    errors, form = {}, {}

    if request.method == "POST":
        form = form_with_user()
        valid_ids = {b["box_type_id"] for b in box_types}
        data, errors = validate_order(form, valid_ids, finishing_ids)

        if not errors:
            conn = get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO orders (
                            order_code, box_type_id, quantity, received_at,
                            promised_date, material_in_stock, material_received_at, finishing,
                            open_orders_at_receipt, entered_by, source
                        )
                        VALUES (
                            %(order_code)s, %(box_type_id)s, %(quantity)s, %(received_at)s,
                            %(promised_date)s, %(material_in_stock)s, %(material_received_at)s,
                            %(finishing)s,
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
                flash(f"№ {data['order_code']} buyurtma saqlandi.", "success")
                return redirect(url_for("main.order_detail", order_id=new_id))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                errors["order_code"] = "Bunday raqamli buyurtma allaqachon mavjud."

    finishing_codes = sorted(FINISHING_BOX_TYPES)
    return render_template(
        "order_form.html",
        box_types=box_types, finishing_codes=finishing_codes, errors=errors, form=form,
    )


@bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = get_order(order_id)
    return render_template(
        "order_detail.html",
        order=order,
        route=get_route(order),
        finishing_label=FINISHING_LABELS[order["finishing"]],
        now_str=now_input(),
    )


@bp.route("/orders/<int:order_id>/material", methods=["POST"])
@login_required
def material_arrived(order_id):
    order = get_order(order_id)
    back = url_for("main.order_detail", order_id=order_id)
    if order["material_in_stock"] or order["material_received_at"]:
        flash("Bu buyurtma uchun xomashyo allaqachon belgilangan.", "warning")
        return redirect(back)

    arrived, error = validate_material_arrival(request.form, to_local(order["received_at"]))
    if error:
        flash(error, "danger")
        return redirect(back)

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orders SET material_received_at = %s, updated_by = %s, updated_at = now()
            WHERE order_id = %s;
            """,
            (arrived, g.user["username"], order_id),
        )
    conn.commit()
    flash("Xomashyo kelgani belgilandi.", "success")
    return redirect(back)


@bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def edit_order(order_id):
    order = get_order(order_id)
    box_types = get_box_types()
    finishing_ids = {b["box_type_id"] for b in box_types if b["code"] in FINISHING_BOX_TYPES}

    cur = get_db().cursor()
    cur.execute(
        "SELECT COUNT(*) AS n, MAX(boxes_completed) AS max_boxes FROM stage_events WHERE order_id = %s;",
        (order_id,),
    )
    recorded = cur.fetchone()
    # The route depends on box type and finishing, so they are fixed once a stage is recorded
    route_locked = recorded["n"] > 0
    errors = {}

    if request.method == "POST":
        form = form_with_user()
        if route_locked:
            form["box_type_id"] = str(order["box_type_id"])
            form["finishing"] = order["finishing"]
        data, errors = validate_order(form, {b["box_type_id"] for b in box_types}, finishing_ids)

        if not errors and recorded["max_boxes"] and data["quantity"] < recorded["max_boxes"]:
            errors["quantity"] = (
                f"Soni bosqichlarda kiritilgan tayyor qutilardan ({recorded['max_boxes']}) kam boʻlishi mumkin emas."
            )
        if not errors and order["completed_at"] and data["received_at"] > to_local(order["completed_at"]):
            errors["received_at"] = "Qabul qilingan vaqt buyurtma tayyor boʻlgan vaqtdan keyin boʻlishi mumkin emas."

        if not errors:
            data["order_id"] = order_id
            conn = get_db()
            try:
                with conn.cursor() as cur2:
                    cur2.execute(
                        """
                        UPDATE orders
                        SET order_code        = %(order_code)s,
                            box_type_id       = %(box_type_id)s,
                            quantity          = %(quantity)s,
                            received_at       = %(received_at)s,
                            promised_date     = %(promised_date)s,
                            material_in_stock = %(material_in_stock)s,
                            material_received_at = %(material_received_at)s,
                            finishing         = %(finishing)s,
                            open_orders_at_receipt = (
                                SELECT COUNT(*) FROM orders o2
                                WHERE o2.order_id <> %(order_id)s
                                  AND o2.received_at <= %(received_at)s
                                  AND (o2.completed_at IS NULL OR o2.completed_at > %(received_at)s)),
                            updated_by        = %(entered_by)s,
                            updated_at        = now()
                        WHERE order_id = %(order_id)s;
                        """,
                        data,
                    )
                conn.commit()
                flash("Buyurtma yangilandi.", "success")
                return redirect(url_for("main.order_detail", order_id=order_id))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                errors["order_code"] = "Bunday raqamli buyurtma allaqachon mavjud."
            except psycopg2.IntegrityError:
                conn.rollback()
                flash("Maʼlumotlar bazasi bu oʻzgarishni qabul qilmadi. Qiymatlarni tekshiring.", "danger")
    else:
        form = {
            "order_code": order["order_code"],
            "box_type_id": str(order["box_type_id"]),
            "quantity": str(order["quantity"]),
            "received_at": to_input_datetime(order["received_at"]),
            "promised_date": order["promised_date"].isoformat() if order["promised_date"] else "",
            "material_in_stock": "yes" if order["material_in_stock"] else "no",
            "material_received_at": to_input_datetime(order["material_received_at"]),
            "finishing": order["finishing"],
        }

    return render_template(
        "order_form.html",
        box_types=box_types, finishing_codes=sorted(FINISHING_BOX_TYPES),
        errors=errors, form=form, editing=order, route_locked=route_locked,
    )


@bp.route("/orders/<int:order_id>/reopen", methods=["POST"])
@login_required
def reopen_order(order_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orders SET completed_at = NULL, completed_by = NULL
            WHERE order_id = %s
            RETURNING order_id;
            """,
            (order_id,),
        )
        if cur.fetchone() is None:
            abort(404)
    conn.commit()
    flash("Buyurtma qayta ochildi.", "success")
    return redirect(url_for("main.order_detail", order_id=order_id))


# ---------- Stages: start and finish ----------

@bp.route("/orders/<int:order_id>/stages/<int:stage_id>/start", methods=["GET", "POST"])
@login_required
def start_stage(order_id, stage_id):
    order = get_order(order_id)
    stage = find_stage(get_route(order), stage_id)
    back = url_for("main.order_detail", order_id=order_id)

    if order["completed_at"] or stage["started_at"]:
        flash("Bu bosqich allaqachon boshlangan.", "warning")
        return redirect(back)

    if request.method == "GET":
        return render_template("stage_start.html", order=order, stage=stage, now_str=now_input())

    now = local_now()
    started_at, error = validate_stage_start(request.form, to_local(order["received_at"]), now)
    if error:
        flash(error, "danger")
        return redirect(back)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stage_events (
                    order_id, stage_id, machine_id, started_at, entry_mode, entered_by, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'web_form');
                """,
                (
                    order_id, stage_id, single_machine_for(stage_id), started_at,
                    "realtime" if now - started_at <= LATE_ENTRY else "end_of_day",
                    g.user["username"],
                ),
            )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        flash("Bu bosqich allaqachon boshlangan.", "warning")
    return redirect(back)


@bp.route("/orders/<int:order_id>/stages/<int:stage_id>/finish", methods=["GET", "POST"])
@login_required
def finish_stage(order_id, stage_id):
    order = get_order(order_id)
    stage = find_stage(get_route(order), stage_id)
    back = url_for("main.order_detail", order_id=order_id)

    if not stage["started_at"] or stage["finished_at"]:
        flash("Bu bosqichni hozir tugatib boʻlmaydi.", "warning")
        return redirect(back)

    errors = {}
    form = {"boxes_completed": str(order["quantity"]), "boxes_defective": "0"}

    if request.method == "POST":
        form = request.form.to_dict()
        now = local_now()
        data, errors = validate_stage_finish(form, to_local(stage["started_at"]), order["quantity"], now)

        if not errors:
            data["late"] = now - data["finished_at"] > LATE_ENTRY
            data["stage_event_id"] = stage["stage_event_id"]
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE stage_events
                    SET finished_at     = %(finished_at)s,
                        boxes_completed = %(boxes_completed)s,
                        boxes_defective = %(boxes_defective)s,
                        operators       = %(operators)s,
                        entry_mode      = CASE WHEN %(late)s THEN 'end_of_day' ELSE entry_mode END
                    WHERE stage_event_id = %(stage_event_id)s;
                    """,
                    data,
                )
            conn.commit()
            if complete_if_all_finished(conn, order):
                flash(f"Barcha bosqichlar tugadi. № {order['order_code']} buyurtma tayyor!", "success")
            else:
                flash(f"{stage['name']}: tugatildi.", "success")
            return redirect(back)

    return render_template(
        "stage_finish.html", order=order, stage=stage, errors=errors, form=form,
    )


# ---------- Stages: correcting a recorded stage ----------

@bp.route("/stages/<int:stage_event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_stage_event(stage_event_id):
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT se.*, s.name AS stage_name,
               o.order_code, o.received_at AS order_received_at
        FROM stage_events se
        JOIN stages s USING (stage_id)
        JOIN orders o USING (order_id)
        WHERE se.stage_event_id = %s;
        """,
        (stage_event_id,),
    )
    stage = cur.fetchone()
    if stage is None:
        abort(404)

    machines = get_machines()
    pairs = get_stage_machine_pairs()
    allowed_pairs = {(p["stage_id"], p["machine_id"]) for p in pairs}
    allowed_ids = {p["machine_id"] for p in pairs if p["stage_id"] == stage["stage_id"]}
    machines_for_stage = [m for m in machines if m["machine_id"] in allowed_ids]

    errors = {}

    if request.method == "POST":
        # Order and stage cannot be changed on edit; the editor is the logged-in user
        form = form_with_user()
        form["order_id"] = str(stage["order_id"])
        form["stage_id"] = str(stage["stage_id"])

        data, errors = validate_stage_event(
            form,
            {stage["order_id"]: to_local(stage["order_received_at"])},
            {stage["stage_id"]},
            {m["machine_id"] for m in machines},
            allowed_pairs=allowed_pairs,
        )

        if not errors:
            data["stage_event_id"] = stage_event_id
            conn = get_db()
            try:
                with conn.cursor() as cur2:
                    cur2.execute(
                        """
                        UPDATE stage_events
                        SET machine_id      = %(machine_id)s,
                            started_at      = %(started_at)s,
                            finished_at     = %(finished_at)s,
                            operators       = %(operators)s,
                            boxes_completed = %(boxes_completed)s,
                            boxes_defective = %(boxes_defective)s,
                            entry_mode      = %(entry_mode)s,
                            updated_by      = %(entered_by)s,
                            updated_at      = now()
                        WHERE stage_event_id = %(stage_event_id)s;
                        """,
                        data,
                    )
                conn.commit()
                flash("Bosqich yangilandi.", "success")
                return redirect(url_for("main.order_detail", order_id=stage["order_id"]))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash("Maʼlumotlar bazasi bu oʻzgarishni qabul qilmadi. Qiymatlarni tekshiring.", "danger")
    else:
        form = {
            "machine_id": str(stage["machine_id"]) if stage["machine_id"] else "",
            "operators": str(stage["operators"]) if stage["operators"] else "",
            "started_at": to_input_datetime(stage["started_at"]),
            "finished_at": to_input_datetime(stage["finished_at"]),
            "boxes_completed": "" if stage["boxes_completed"] is None else str(stage["boxes_completed"]),
            "boxes_defective": "" if stage["boxes_defective"] is None else str(stage["boxes_defective"]),
            "entry_mode": stage["entry_mode"],
        }

    return render_template(
        "stage_edit.html",
        stage=stage, machines_for_stage=machines_for_stage,
        errors=errors, form=form,
    )
