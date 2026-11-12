from datetime import datetime, date, timedelta

MAX_QUANTITY = 10_000_000


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value):
    try:
        return datetime.fromisoformat(value or "")
    except ValueError:
        return None


def _parse_optional_count(form, field, label, errors):
    raw = form.get(field) or ""
    if raw == "":
        return None
    value = _parse_int(raw)
    if value is None or value < 0:
        errors[field] = f"{label} 0 yoki undan katta butun son boʻlishi kerak."
        return None
    return value


def validate_order(form, valid_box_type_ids, now=None):
    """Check order form input. Returns (clean_data, errors)."""
    now = now or datetime.now()
    errors = {}
    data = {}

    code = (form.get("order_code") or "").strip().upper()
    if not code:
        errors["order_code"] = "Buyurtma raqamini kiriting."
    elif len(code) > 30:
        errors["order_code"] = "Buyurtma raqami 30 belgidan oshmasligi kerak."
    data["order_code"] = code

    box_type_id = _parse_int(form.get("box_type_id"))
    if box_type_id not in valid_box_type_ids:
        errors["box_type_id"] = "Quti turini tanlang."
    data["box_type_id"] = box_type_id

    quantity = _parse_int(form.get("quantity"))
    if quantity is None or quantity <= 0:
        errors["quantity"] = "Soni musbat butun son boʻlishi kerak."
    elif quantity > MAX_QUANTITY:
        errors["quantity"] = f"Soni {MAX_QUANTITY:,} dan oshmasligi kerak."
    data["quantity"] = quantity

    received_at = _parse_datetime(form.get("received_at"))
    if received_at is None:
        errors["received_at"] = "Toʻgʻri sana va vaqtni kiriting."
    elif received_at > now + timedelta(minutes=5):
        errors["received_at"] = "Qabul qilingan vaqt kelajakda boʻlishi mumkin emas."
    data["received_at"] = received_at

    promised = None
    promised_raw = form.get("promised_date") or ""
    if promised_raw:
        try:
            promised = date.fromisoformat(promised_raw)
        except ValueError:
            errors["promised_date"] = "Toʻgʻri sanani kiriting."
        if promised and received_at and promised < received_at.date():
            errors["promised_date"] = "Vaʼda qilingan sana qabul qilingan sanadan oldin boʻlishi mumkin emas."
    data["promised_date"] = promised

    stock = form.get("material_in_stock")
    if stock not in ("yes", "no"):
        errors["material_in_stock"] = "Xomashyo omborda bor-yoʻqligini belgilang."
    data["material_in_stock"] = stock == "yes"

    entered_by = (form.get("entered_by") or "").strip()
    if not entered_by:
        errors["entered_by"] = "Kiritgan shaxs koʻrsatilmagan."
    data["entered_by"] = entered_by

    return data, errors


def validate_stage_event(form, orders, valid_stage_ids, valid_machine_ids,
                         allowed_pairs=None, now=None):
    """Check stage event input.

    orders: dict {order_id: received_at} for orders that are still open.
    allowed_pairs: set of (stage_id, machine_id) that are permitted.
    Returns (clean_data, errors).
    """
    now = now or datetime.now()
    errors = {}
    data = {}

    order_id = _parse_int(form.get("order_id"))
    if order_id not in orders:
        errors["order_id"] = "Ochiq buyurtmani tanlang."
    data["order_id"] = order_id

    stage_id = _parse_int(form.get("stage_id"))
    if stage_id not in valid_stage_ids:
        errors["stage_id"] = "Bosqichni tanlang."
    data["stage_id"] = stage_id

    machine_id = None
    if form.get("machine_id"):
        machine_id = _parse_int(form.get("machine_id"))
        if machine_id not in valid_machine_ids:
            errors["machine_id"] = "Stanokni tanlang."
        elif allowed_pairs is not None and (stage_id, machine_id) not in allowed_pairs:
            errors["machine_id"] = "Bu stanok tanlangan bosqich uchun ishlatilmaydi."
    data["machine_id"] = machine_id

    started_at = _parse_datetime(form.get("started_at"))
    if started_at is None:
        errors["started_at"] = "Boshlanish sana va vaqtini toʻgʻri kiriting."
    elif started_at > now + timedelta(minutes=5):
        errors["started_at"] = "Boshlanish vaqti kelajakda boʻlishi mumkin emas."
    elif order_id in orders and started_at < orders[order_id]:
        errors["started_at"] = "Bosqich buyurtma qabul qilinishidan oldin boshlanishi mumkin emas."
    data["started_at"] = started_at

    finished_at = None
    if form.get("finished_at"):
        finished_at = _parse_datetime(form.get("finished_at"))
        if finished_at is None:
            errors["finished_at"] = "Tugash sana va vaqtini toʻgʻri kiriting."
        elif finished_at > now + timedelta(minutes=5):
            errors["finished_at"] = "Tugash vaqti kelajakda boʻlishi mumkin emas."
        elif started_at and finished_at <= started_at:
            errors["finished_at"] = "Tugash vaqti boshlanish vaqtidan keyin boʻlishi kerak."
    data["finished_at"] = finished_at

    operators = None
    if form.get("operators"):
        operators = _parse_int(form.get("operators"))
        if operators not in (1, 2):
            errors["operators"] = "Operatorlar soni 1 yoki 2 boʻlishi kerak."
    data["operators"] = operators

    completed = _parse_optional_count(form, "boxes_completed", "Tayyor qutilar soni", errors)
    defective = _parse_optional_count(form, "boxes_defective", "Brak qutilar soni", errors)
    if completed is not None and defective is not None and defective > completed:
        errors["boxes_defective"] = "Brak qutilar soni tayyor qutilardan koʻp boʻlishi mumkin emas."
    if finished_at and completed is None and "boxes_completed" not in errors:
        errors["boxes_completed"] = "Bosqich tugagan boʻlsa, tayyor qutilar sonini kiriting."
    data["boxes_completed"] = completed
    data["boxes_defective"] = defective

    entry_mode = form.get("entry_mode") or "realtime"
    if entry_mode not in ("realtime", "end_of_day"):
        errors["entry_mode"] = "Kiritish usulini tanlang."
    data["entry_mode"] = entry_mode

    entered_by = (form.get("entered_by") or "").strip()
    if not entered_by:
        errors["entered_by"] = "Kiritgan shaxs koʻrsatilmagan."
    data["entered_by"] = entered_by

    return data, errors