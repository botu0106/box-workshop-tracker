-- Safe to run more than once: existing rows keep their IDs and get updated names.
-- Stages, machines and routes confirmed by the workshop manager on 12 Nov 2026.

INSERT INTO box_types (code, name) VALUES
  ('PLAIN',   'Oddiy quti'),
  ('STENCIL', 'Trafaret bosmali quti'),
  ('OFFSET',  'Rangli (ofset) quti'),
  ('MICRO',   'Mikro quti / qadoq')
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;

INSERT INTO stages (code, name) VALUES
  ('CORRUGATE', 'Gofrokarton kesish'),
  ('PAPERCUT',  'Qogʻoz kesish'),
  ('STENCIL',   'Trafaret bosma'),
  ('OFFSET',    'Ofset bosma'),
  ('DRYING',    'Boʻyoq quritish'),
  ('LAMINATE',  'Laminatsiya'),
  ('LACQUER',   'Laklash'),
  ('MOUNT',     'Kleyvalda yelimlash (qatlamlar / ofset)'),
  ('DIECUT',    'Shtamplash / shakl berish'),
  ('GLUING',    'Yelimlash (qoʻlda)'),
  ('PRESS',     'Presslash')
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;

-- One machine of each type (confirmed). The waste-paper press is not part of production.
INSERT INTO machines (code, machine_type) VALUES
  ('M01', 'Gofroagregat'),
  ('M02', 'Qogʻoz kesish stanogi'),
  ('M03', 'Trafaret bosma stanogi'),
  ('M04', 'Ofset bosma stanogi'),
  ('M05', 'Laminator'),
  ('M06', 'Laklash stanogi'),
  ('M07', 'Qogʻoz pressi'),
  ('M08', 'Shtamplash / shakl berish stanogi'),
  ('M09', 'Kleyval'),
  ('M10', 'Qoʻlda yelimlash')
ON CONFLICT (code) DO UPDATE SET machine_type = EXCLUDED.machine_type;

-- Remove pairs the manager confirmed are wrong (only if no records use them yet)
DELETE FROM stage_machines sm
USING stages s, machines m
WHERE sm.stage_id = s.stage_id
  AND sm.machine_id = m.machine_id
  AND (s.code, m.code) IN (('MOUNT', 'M07'), ('GLUING', 'M09'))
  AND NOT EXISTS (
      SELECT 1 FROM stage_events se
      WHERE se.stage_id = sm.stage_id AND se.machine_id = sm.machine_id
  );

-- Which machine performs which stage (drying has no machine)
INSERT INTO stage_machines (stage_id, machine_id)
SELECT s.stage_id, m.machine_id
FROM (VALUES
    ('CORRUGATE', 'M01'),
    ('PAPERCUT',  'M02'),
    ('STENCIL',   'M03'),
    ('OFFSET',    'M04'),
    ('LAMINATE',  'M05'),
    ('LACQUER',   'M06'),
    ('PRESS',     'M07'),
    ('DIECUT',    'M08'),
    ('MOUNT',     'M09'),
    ('GLUING',    'M10')
) AS pairs(stage_code, machine_code)
JOIN stages s   ON s.code = pairs.stage_code
JOIN machines m ON m.code = pairs.machine_code
ON CONFLICT DO NOTHING;

-- Route of each box type. Lamination and lacquering are listed for colour and micro boxes,
-- but an order only shows the one the client chose (or neither).
-- Drying after stencil printing happens only for hand printing, so it is not in the route.
INSERT INTO box_type_routes (box_type_id, stage_id, position)
SELECT b.box_type_id, s.stage_id, r.position
FROM (VALUES
    ('PLAIN',   'CORRUGATE', 1),
    ('PLAIN',   'MOUNT',     2),
    ('PLAIN',   'PRESS',     3),
    ('PLAIN',   'DIECUT',    4),
    ('PLAIN',   'GLUING',    5),

    ('STENCIL', 'CORRUGATE', 1),
    ('STENCIL', 'MOUNT',     2),
    ('STENCIL', 'PRESS',     3),
    ('STENCIL', 'STENCIL',   4),
    ('STENCIL', 'DIECUT',    5),
    ('STENCIL', 'GLUING',    6),

    ('OFFSET',  'PAPERCUT',  1),
    ('OFFSET',  'OFFSET',    2),
    ('OFFSET',  'DRYING',    3),
    ('OFFSET',  'LAMINATE',  4),
    ('OFFSET',  'LACQUER',   5),
    ('OFFSET',  'CORRUGATE', 6),
    ('OFFSET',  'MOUNT',     7),
    ('OFFSET',  'PRESS',     8),
    ('OFFSET',  'DIECUT',    9),
    ('OFFSET',  'GLUING',    10),

    ('MICRO',   'PAPERCUT',  1),
    ('MICRO',   'OFFSET',    2),
    ('MICRO',   'DRYING',    3),
    ('MICRO',   'LAMINATE',  4),
    ('MICRO',   'LACQUER',   5),
    ('MICRO',   'DIECUT',    6),
    ('MICRO',   'GLUING',    7)
) AS r(box_code, stage_code, position)
JOIN box_types b ON b.code = r.box_code
JOIN stages s    ON s.code = r.stage_code
ON CONFLICT (box_type_id, stage_id) DO UPDATE SET position = EXCLUDED.position;
