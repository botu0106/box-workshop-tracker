INSERT INTO box_types (code, name) VALUES
  ('PLAIN',   'Plain corrugated box'),
  ('STENCIL', 'Stencil-printed box'),
  ('OFFSET',  'Multi-colour offset box'),
  ('MICRO',   'Micro box / packaging');

INSERT INTO stages (code, name) VALUES
  ('CORRUGATE', 'Corrugated board cutting'),
  ('PAPERCUT',  'Paper cutting'),
  ('STENCIL',   'Stencil printing'),
  ('OFFSET',    'Offset printing'),
  ('DRYING',    'Ink drying'),
  ('LAMINATE',  'Film lamination'),
  ('LACQUER',   'Lacquering'),
  ('MOUNT',     'Mounting print onto corrugated board'),
  ('DIECUT',    'Die-cutting / forming'),
  ('GLUING',    'Gluing');

-- Machine list based on the workshop's answers (to be confirmed with the manager)
INSERT INTO machines (code, machine_type) VALUES
  ('M01', 'Corrugating machine'),
  ('M02', 'Paper cutting machine'),
  ('M03', 'Stencil printing machine'),
  ('M04', 'Offset printing machine'),
  ('M05', 'Laminating machine'),
  ('M06', 'Lacquering machine'),
  ('M07', 'Paper press'),
  ('M08', 'Die-cutting / forming machine'),
  ('M09', 'Gluing machine (semi-automatic)'),
  ('M10', 'Gluing machine (manual)');

-- Which machine can perform which stage (to be confirmed with the manager)
INSERT INTO stage_machines (stage_id, machine_id)
SELECT s.stage_id, m.machine_id
FROM (VALUES
    ('CORRUGATE', 'M01'),
    ('PAPERCUT',  'M02'),
    ('STENCIL',   'M03'),
    ('OFFSET',    'M04'),
    ('LAMINATE',  'M05'),
    ('LACQUER',   'M06'),
    ('MOUNT',     'M07'),
    ('DIECUT',    'M08'),
    ('GLUING',    'M09'),
    ('GLUING',    'M10')
) AS pairs(stage_code, machine_code)
JOIN stages s   ON s.code = pairs.stage_code
JOIN machines m ON m.code = pairs.machine_code;