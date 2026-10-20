-- Reference tables
CREATE TABLE box_types (
    box_type_id SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL
);

CREATE TABLE stages (
    stage_id SERIAL PRIMARY KEY,
    code     TEXT UNIQUE NOT NULL,
    name     TEXT NOT NULL
);

CREATE TABLE machines (
    machine_id   SERIAL PRIMARY KEY,
    code         TEXT UNIQUE NOT NULL,
    machine_type TEXT NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Orders
CREATE TABLE orders (
    order_id               SERIAL PRIMARY KEY,
    order_code             TEXT UNIQUE NOT NULL,
    box_type_id            INT NOT NULL REFERENCES box_types(box_type_id),
    quantity               INT NOT NULL CHECK (quantity > 0),
    received_at            TIMESTAMPTZ NOT NULL,
    promised_date          DATE,
    material_in_stock      BOOLEAN NOT NULL,
    open_orders_at_receipt INT NOT NULL CHECK (open_orders_at_receipt >= 0),
    completed_at           TIMESTAMPTZ,
    entered_by             TEXT NOT NULL,
    source                 TEXT NOT NULL DEFAULT 'web_form',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (completed_at IS NULL OR completed_at >= received_at)
);

-- Production stage events
CREATE TABLE stage_events (
    stage_event_id  SERIAL PRIMARY KEY,
    order_id        INT NOT NULL REFERENCES orders(order_id),
    stage_id        INT NOT NULL REFERENCES stages(stage_id),
    machine_id      INT REFERENCES machines(machine_id),
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    operators       SMALLINT CHECK (operators IN (1, 2)),
    boxes_completed INT CHECK (boxes_completed >= 0),
    boxes_defective INT CHECK (boxes_defective >= 0),
    entry_mode      TEXT NOT NULL DEFAULT 'realtime'
                    CHECK (entry_mode IN ('realtime', 'end_of_day')),
    entered_by      TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'web_form',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (finished_at IS NULL OR finished_at > started_at),
    CHECK (boxes_defective IS NULL OR boxes_completed IS NULL
           OR boxes_defective <= boxes_completed)
);

CREATE INDEX idx_stage_events_order   ON stage_events(order_id);
CREATE INDEX idx_stage_events_started ON stage_events(started_at);