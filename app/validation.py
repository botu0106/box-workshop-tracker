from datetime import datetime, date, timedelta

MAX_QUANTITY = 10_000_000


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_order(form, valid_box_type_ids, now=None):
    """Check order form input. Returns (clean_data, errors)."""
    now = now or datetime.now()
    errors = {}
    data = {}

    code = (form.get("order_code") or "").strip().upper()
    if not code:
        errors["order_code"] = "Order code is required."
    elif len(code) > 30:
        errors["order_code"] = "Order code must be at most 30 characters."
    data["order_code"] = code

    box_type_id = _parse_int(form.get("box_type_id"))
    if box_type_id not in valid_box_type_ids:
        errors["box_type_id"] = "Choose a valid box type."
    data["box_type_id"] = box_type_id

    quantity = _parse_int(form.get("quantity"))
    if quantity is None or quantity <= 0:
        errors["quantity"] = "Quantity must be a positive whole number."
    elif quantity > MAX_QUANTITY:
        errors["quantity"] = f"Quantity must not exceed {MAX_QUANTITY:,}."
    data["quantity"] = quantity

    received_at = None
    try:
        received_at = datetime.fromisoformat(form.get("received_at") or "")
    except ValueError:
        errors["received_at"] = "Enter a valid date and time."
    if received_at and received_at > now + timedelta(minutes=5):
        errors["received_at"] = "Received time cannot be in the future."
    data["received_at"] = received_at

    promised = None
    promised_raw = form.get("promised_date") or ""
    if promised_raw:
        try:
            promised = date.fromisoformat(promised_raw)
        except ValueError:
            errors["promised_date"] = "Enter a valid date."
        if promised and received_at and promised < received_at.date():
            errors["promised_date"] = "Promised date cannot be before the order was received."
    data["promised_date"] = promised

    stock = form.get("material_in_stock")
    if stock not in ("yes", "no"):
        errors["material_in_stock"] = "Select whether material is in stock."
    data["material_in_stock"] = stock == "yes"

    entered_by = (form.get("entered_by") or "").strip()
    if not entered_by:
        errors["entered_by"] = "Entered by is required."
    data["entered_by"] = entered_by

    return data, errors