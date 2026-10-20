INSERT INTO box_types (code, name) VALUES
  ('PLAIN',   'Plain corrugated box'),
  ('STENCIL', 'Stencil-printed box'),
  ('OFFSET',  'Multi-colour offset box'),
  ('MICRO',   'Micro box / packaging');

INSERT INTO stages (code, name) VALUES
  ('CORRUGATE', 'Corrugated board cutting'),
  ('STENCIL',   'Stencil printing'),
  ('OFFSET',    'Offset printing'),
  ('DRYING',    'Ink drying'),
  ('LAMINATE',  'Laminating print onto corrugated board'),
  ('DIECUT',    'Die-cutting / forming'),
  ('GLUING',    'Gluing');

INSERT INTO machines (code, machine_type) VALUES
  ('M1', 'Corrugating machine'),
  ('M2', 'Gluing machine (semi-automatic)'),
  ('M3', 'Gluing machine (manual)'),
  ('M4', 'Die-cutting / forming machine'),
  ('M5', 'Offset printing machine'),
  ('M6', 'Paper cutting machine');