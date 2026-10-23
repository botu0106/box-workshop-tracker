"""Unit tests for input validation (no database needed)."""
from datetime import datetime

import pytest

from app.validation import validate_order, validate_stage_event

NOW = datetime(2026, 10, 25, 12, 0)
BOX_TYPES = {1, 2, 3, 4}


# ---------- Orders ----------

def order_form(**overrides):
    form = {
        "order_code": "a-101",
        "box_type_id": "1",
        "quantity": "1000",
        "received_at": "2026-10-20T09:00",
        "promised_date": "2026-10-27",
        "material_in_stock": "yes",
        "entered_by": "manager",
    }
    form.update(overrides)
    return form


def test_valid_order_is_accepted_and_code_is_uppercased():
    data, errors = validate_order(order_form(), BOX_TYPES, now=NOW)
    assert errors == {}
    assert data["order_code"] == "A-101"
    assert data["material_in_stock"] is True


@pytest.mark.parametrize("quantity", ["0", "-5", "abc", ""])
def test_invalid_quantity_is_rejected(quantity):
    _, errors = validate_order(order_form(quantity=quantity), BOX_TYPES, now=NOW)
    assert "quantity" in errors


def test_future_received_time_is_rejected():
    _, errors = validate_order(order_form(received_at="2026-10-26T09:00"), BOX_TYPES, now=NOW)
    assert "received_at" in errors


def test_promised_date_before_received_date_is_rejected():
    _, errors = validate_order(order_form(promised_date="2026-10-19"), BOX_TYPES, now=NOW)
    assert "promised_date" in errors


def test_unknown_box_type_is_rejected():
    _, errors = validate_order(order_form(box_type_id="99"), BOX_TYPES, now=NOW)
    assert "box_type_id" in errors


# ---------- Stage events ----------

ORDERS = {1: datetime(2026, 10, 20, 9, 0)}   # order 1 received 20 Oct 09:00
STAGES = {1, 10}                              # 1 = cutting, 10 = gluing
MACHINES = {1, 9, 10}
PAIRS = {(1, 1), (10, 9), (10, 10)}           # allowed (stage, machine) pairs


def stage_form(**overrides):
    form = {
        "order_id": "1",
        "stage_id": "10",
        "machine_id": "9",
        "started_at": "2026-10-21T09:00",
        "finished_at": "2026-10-21T10:00",
        "operators": "1",
        "boxes_completed": "1000",
        "boxes_defective": "5",
        "entry_mode": "realtime",
        "entered_by": "manager",
    }
    form.update(overrides)
    return form


def validate_stage(form):
    return validate_stage_event(form, ORDERS, STAGES, MACHINES, allowed_pairs=PAIRS, now=NOW)


def test_valid_stage_is_accepted():
    data, errors = validate_stage(stage_form())
    assert errors == {}
    assert data["boxes_completed"] == 1000


def test_finish_before_start_is_rejected():
    _, errors = validate_stage(stage_form(finished_at="2026-10-21T08:00"))
    assert "finished_at" in errors


def test_more_defects_than_completed_is_rejected():
    _, errors = validate_stage(stage_form(boxes_completed="100", boxes_defective="150"))
    assert "boxes_defective" in errors


def test_machine_not_allowed_for_stage_is_rejected():
    # machine 1 is a cutting machine and cannot be used for gluing (stage 10)
    _, errors = validate_stage(stage_form(machine_id="1"))
    assert "machine_id" in errors


def test_stage_starting_before_order_received_is_rejected():
    _, errors = validate_stage(stage_form(started_at="2026-10-19T09:00",
                                          finished_at="2026-10-19T10:00"))
    assert "started_at" in errors


def test_finished_stage_without_quantity_is_rejected():
    _, errors = validate_stage(stage_form(boxes_completed=""))
    assert "boxes_completed" in errors