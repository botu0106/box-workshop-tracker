-- Stakeholder queries and data-quality checks for the workshop owner.
-- Run locally:  docker compose exec -T db psql -U workshop -d workshop_db < db/queries.sql

-- Q1. Open orders and how long they have been in production
SELECT o.order_code, b.name AS box_type, o.quantity, o.received_at,
       ROUND((EXTRACT(EPOCH FROM (now() - o.received_at)) / 86400)::numeric, 1) AS days_open,
       o.promised_date
FROM orders o
JOIN box_types b USING (box_type_id)
WHERE o.completed_at IS NULL
ORDER BY o.received_at;

-- Q2. Average duration of each stage in hours (finished stages only)
SELECT s.name AS stage, COUNT(*) AS records,
       ROUND(AVG(EXTRACT(EPOCH FROM (se.finished_at - se.started_at)) / 3600)::numeric, 2) AS avg_hours
FROM stage_events se
JOIN stages s USING (stage_id)
WHERE se.finished_at IS NOT NULL
GROUP BY s.stage_id, s.name
ORDER BY s.stage_id;

-- Q3. Defect rate by box type.
-- Defect rate of an order = all defective boxes recorded on its stages / ordered quantity.
-- Averaged per order, so one large order does not dominate the result.
WITH order_defects AS (
    SELECT o.order_id, o.box_type_id,
           COALESCE(SUM(se.boxes_defective), 0)::numeric / o.quantity AS defect_rate
    FROM orders o
    JOIN stage_events se USING (order_id)
    GROUP BY o.order_id, o.box_type_id, o.quantity
)
SELECT b.name AS box_type, COUNT(*) AS orders,
       ROUND(100 * AVG(od.defect_rate), 2) AS avg_defect_rate_pct
FROM order_defects od
JOIN box_types b USING (box_type_id)
GROUP BY b.name
ORDER BY b.name;

-- Q4. Lead time of completed orders by box type and material availability (days)
SELECT b.name AS box_type, o.material_in_stock, COUNT(*) AS orders,
       ROUND(AVG(EXTRACT(EPOCH FROM (o.completed_at - o.received_at)) / 86400)::numeric, 2) AS avg_lead_days
FROM orders o
JOIN box_types b USING (box_type_id)
WHERE o.completed_at IS NOT NULL
GROUP BY b.name, o.material_in_stock
ORDER BY b.name, o.material_in_stock;

-- Q5. Open orders at risk: promised date is tomorrow or already passed
SELECT o.order_code, o.promised_date,
       (o.promised_date - CURRENT_DATE) AS days_left,
       (SELECT s.name FROM stage_events se JOIN stages s USING (stage_id)
         WHERE se.order_id = o.order_id
         ORDER BY se.started_at DESC LIMIT 1) AS last_stage
FROM orders o
WHERE o.completed_at IS NULL
  AND o.promised_date IS NOT NULL
  AND o.promised_date <= CURRENT_DATE + 1
ORDER BY o.promised_date;

-- Q6. Machine busy hours in the last 7 days
SELECT m.code, m.machine_type,
       ROUND(COALESCE(SUM(EXTRACT(EPOCH FROM (se.finished_at - se.started_at)) / 3600), 0)::numeric, 1) AS busy_hours
FROM machines m
LEFT JOIN stage_events se
       ON se.machine_id = m.machine_id
      AND se.finished_at IS NOT NULL
      AND se.started_at >= now() - INTERVAL '7 days'
GROUP BY m.machine_id, m.code, m.machine_type
ORDER BY m.code;

-- DQ1. Stages still open for more than 24 hours (probably forgotten)
SELECT o.order_code, s.name AS stage, se.started_at
FROM stage_events se
JOIN orders o USING (order_id)
JOIN stages s USING (stage_id)
WHERE se.finished_at IS NULL
  AND se.started_at < now() - INTERVAL '24 hours'
ORDER BY se.started_at;

-- DQ2. Share of stage records entered later rather than in real time
SELECT entry_mode, COUNT(*) AS records,
       ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 1) AS pct
FROM stage_events
GROUP BY entry_mode;

-- DQ3. The same stage recorded more than once for an order (should be empty)
SELECT o.order_code, s.name AS stage, COUNT(*) AS records
FROM stage_events se
JOIN orders o USING (order_id)
JOIN stages s USING (stage_id)
GROUP BY o.order_code, s.name
HAVING COUNT(*) > 1;

-- DQ4. Stages that report more boxes than were ordered (should be empty)
SELECT o.order_code, s.name AS stage, se.boxes_completed, o.quantity
FROM stage_events se
JOIN orders o USING (order_id)
JOIN stages s USING (stage_id)
WHERE se.boxes_completed > o.quantity;