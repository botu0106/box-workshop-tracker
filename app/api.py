"""JSON REST API, version 1.

Uses the same session login and the same validation as the web pages. Write requests
must send the session's CSRF token in the X-CSRF-Token header (GET /api/v1/session
returns it). Documented in docs/api.md.
"""
import psycopg2
from flask import Blueprint, g, jsonify, request, url_for

from . import services
from .auth import login_required, owner_required
from .db import get_db
from .routes import (
    FINISHING_BOX_TYPES, LATE_ENTRY, entry_mode_for, find_stage, get_box_types, get_order,
    get_route, single_machine_for,
)
from .security import csrf_token
from .validation import (
    local_now, to_local, validate_order, validate_stage_finish, validate_stage_start,
)

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _iso(value):
    return to_local(value).isoformat(timespec="minutes") if value else None


def order_json(order, route=None):
    data = {
        "id": order["order_id"],
        "order_code": order["order_code"],
        "box_type": order["box_code"],
        "quantity": order["quantity"],
        "finishing": order["finishing"],
        "material_in_stock": order["material_in_stock"],
        "material_received_at": _iso(order["material_received_at"]),
        "received_at": _iso(order["received_at"]),
        "promised_date": order["promised_date"].isoformat() if order["promised_date"] else None,
        "completed_at": _iso(order["completed_at"]),
        "status": "completed" if order["completed_at"] else "open",
        "entered_by": order["entered_by"],
        "url": url_for("api.get_order_json", order_id=order["order_id"]),
    }
    if route is not None:
        data["stages"] = [
            {
                "stage_id": s["stage_id"],
                "code": s["code"],
                "name": s["name"],
                "machine": s["machine_code"],
                "started_at": _iso(s["started_at"]),
                "finished_at": _iso(s["finished_at"]),
                "boxes_completed": s["boxes_completed"],
                "boxes_defective": s["boxes_defective"],
                "operators": s["operators"],
                "status": "finished" if s["finished_at"] else "running" if s["started_at"] else "waiting",
            }
            for s in route
        ]
    return data


def _body():
    """JSON body as a dict of strings, the shape the validators expect."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None
    form = {}
    for key, value in body.items():
        if isinstance(value, bool):
            form[key] = "yes" if value else "no"
        elif value is not None:
            form[key] = str(value)
    return form


def _validate_order_body(form):
    box_types = get_box_types()
    by_code = {b["code"]: b["box_type_id"] for b in box_types}
    if "box_type" in form:  # the API names box types by code, e.g. "OFFSET"
        form["box_type_id"] = str(by_code.get(form["box_type"].upper(), ""))
    finishing_ids = {by_code[c] for c in FINISHING_BOX_TYPES}
    form["entered_by"] = g.user["username"]
    return validate_order(form, set(by_code.values()), finishing_ids)


@bp.route("/session")
@login_required
def session_info():
    return jsonify(username=g.user["username"], role=g.user["role"], csrf_token=csrf_token())


@bp.route("/orders")
@login_required
def list_orders_json():
    status = request.args.get("status")
    where = {"open": "WHERE o.completed_at IS NULL", "completed": "WHERE o.completed_at IS NOT NULL"}
    if status not in (None, "open", "completed"):
        return jsonify(error="status must be 'open' or 'completed'."), 400
    cur = get_db().cursor()
    cur.execute(services.ORDER_SELECT + where.get(status, "") + " ORDER BY o.received_at DESC;")
    return jsonify(orders=[order_json(o) for o in cur.fetchall()])


@bp.route("/orders", methods=["POST"])
@login_required
def create_order_json():
    form = _body()
    if form is None:
        return jsonify(error="Send a JSON object."), 400
    data, errors = _validate_order_body(form)
    if errors:
        return jsonify(errors=errors), 422
    try:
        order_id = services.create_order(data, source="api")
    except psycopg2.errors.UniqueViolation:
        return jsonify(errors={"order_code": "An order with this code already exists."}), 409
    order = get_order(order_id)
    response = jsonify(order_json(order, get_route(order)))
    response.status_code = 201
    response.headers["Location"] = url_for("api.get_order_json", order_id=order_id)
    return response


@bp.route("/orders/<int:order_id>")
@login_required
def get_order_json(order_id):
    order = get_order(order_id)
    return jsonify(order_json(order, get_route(order)))


@bp.route("/orders/<int:order_id>", methods=["PUT"])
@login_required
def update_order_json(order_id):
    order = get_order(order_id)
    form = _body()
    if form is None:
        return jsonify(error="Send a JSON object."), 400
    if any(s["started_at"] for s in get_route(order)):
        # The route depends on these, so they are fixed once a stage is recorded
        form["box_type"] = order["box_code"]
        form["finishing"] = order["finishing"]
    data, errors = _validate_order_body(form)
    if errors:
        return jsonify(errors=errors), 422
    try:
        services.update_order(order_id, data)
    except psycopg2.errors.UniqueViolation:
        return jsonify(errors={"order_code": "An order with this code already exists."}), 409
    order = get_order(order_id)
    return jsonify(order_json(order, get_route(order)))


@bp.route("/orders/<int:order_id>", methods=["DELETE"])
@owner_required
def delete_order_json(order_id):
    get_order(order_id)  # 404 if it does not exist
    services.delete_order(order_id)
    return "", 204


@bp.route("/orders/<int:order_id>/stages/<int:stage_id>/start", methods=["POST"])
@login_required
def start_stage_json(order_id, stage_id):
    order = get_order(order_id)
    stage = find_stage(get_route(order), stage_id)
    if order["completed_at"] or stage["started_at"]:
        return jsonify(error="This stage has already been started."), 409
    form = _body() or {}
    now = local_now()
    started_at, error = validate_stage_start(form, to_local(order["received_at"]), now)
    if error:
        return jsonify(errors={"started_at": error}), 422
    try:
        services.start_stage(
            order_id, stage_id, single_machine_for(stage_id), started_at,
            entry_mode_for(started_at, now), g.user["username"], source="api",
        )
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="This stage has already been started."), 409
    order = get_order(order_id)
    return jsonify(order_json(order, get_route(order))), 201


@bp.route("/orders/<int:order_id>/stages/<int:stage_id>/finish", methods=["POST"])
@login_required
def finish_stage_json(order_id, stage_id):
    order = get_order(order_id)
    stage = find_stage(get_route(order), stage_id)
    if not stage["started_at"] or stage["finished_at"]:
        return jsonify(error="Only a running stage can be finished."), 409
    form = _body()
    if form is None:
        return jsonify(error="Send a JSON object."), 400
    now = local_now()
    data, errors = validate_stage_finish(form, to_local(stage["started_at"]), order["quantity"], now)
    if errors:
        return jsonify(errors=errors), 422
    services.finish_stage(stage["stage_event_id"], data, late=now - data["finished_at"] > LATE_ENTRY)
    services.complete_if_all_finished(order, get_route(order), g.user["username"])
    order = get_order(order_id)
    return jsonify(order_json(order, get_route(order)))
