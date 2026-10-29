-- Reference tables
CREATE TABLE IF NOT EXISTS box_types (
    box_type_id SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    stage_id SERIAL PRIMARY KEY,
    code     TEXT UNIQUE NOT NULL,
    name     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    machine_id   SERIAL PRIMARY KEY,
    code         TEXT UNIQUE NOT NULL,
    machine_type TEXT NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Which machines can perform which stage
CREATE TABLE IF NOT EXISTS stage_machines (
    stage_id   INT NOT NULL REFERENCES stages(stage_id),
    machine_id INT NOT NULL REFERENCES machines(machine_id),
    PRIMARY KEY (stage_id, machine_id)
);

-- Users who can log in (passwords stored only as hashes)
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL
                  CHECK (username = lower(username) AND length(username) BETWEEN 3 AND 30),
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'manager' CHECK (role IN ('manager', 'owner')),
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
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
CREATE TABLE IF NOT EXISTS stage_events (
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
    updated_by      TEXT,
    updated_at      TIMESTAMPTZ,
    CHECK (finished_at IS NULL OR finished_at > started_at),
    CHECK (boxes_defective IS NULL OR boxes_completed IS NULL
           OR boxes_defective <= boxes_completed),
    FOREIGN KEY (stage_id, machine_id) REFERENCES stage_machines(stage_id, machine_id)
);

CREATE INDEX IF NOT EXISTS idx_stage_events_order   ON stage_events(order_id);
CREATE INDEX IF NOT EXISTS idx_stage_events_started ON stage_events(started_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_code_ci ON orders (UPPER(order_code));