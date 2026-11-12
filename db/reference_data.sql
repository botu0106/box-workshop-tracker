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