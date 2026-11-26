# Quti hisobi – Box Workshop Production Tracker

A web application for a small corrugated box workshop. The workshop manager records
orders and production stages from a phone; the owner manages users and sees the data.
The collected data are analysed to find production bottlenecks and to predict order
lead time.

**Live application:** https://<your-app>.onrender.com
**Repository:** https://github.com/<your-login>/box-workshop-tracker

The user interface is in **Uzbek**, because the workshop manager works in Uzbek. Code,
documentation and reports are in English. Key labels: *Buyurtmalar* = Orders,
*Yangi buyurtma* = New order, *Boshlash* / *Tugatish* = Start / Finish a stage,
*Kirish* = Log in, *Tahrirlash* = Edit. *Kleyval* is the workshop's name for the machine
that bonds corrugated layers and mounts offset prints onto board.

---

## One system, two modules

This repository is the shared basis of two modules, as agreed with both module leaders.
Each module assesses different work, documented in its own folder.

| Part | Shared | Data Science (UDE5014CM) | Web Development (UDE5007CM) |
|---|---|---|---|
| Workshop context and problem | ✓ | | |
| PostgreSQL schema (`db/`) | ✓ | | |
| Order and stage data entry pages | ✓ | | |
| Data validation, provenance, data-quality checks (`db/queries.sql`) | | ✓ | |
| Analysis pipeline: tests, models, figures (`analysis/`) | | ✓ | |
| Checkpoints and evidence register | | ✓ | |
| Registration, login, roles, password hashing (`app/auth.py`) | | | ✓ |
| REST API (`app/api.py`) | | | ✓ |
| Security: CSRF, headers, throttling, error pages (`app/security.py`) | | | ✓ |
| Responsive UI, client-side validation (`app/templates/`) | | | ✓ |
| Cloud deployment (Render + Neon) | | | ✓ |
| Report | | own report | own report |

### Data Science documents – `docs/data-science/`
- [Checkpoint 1](docs/data-science/checkpoint-1.md)
- [Checkpoint 2](docs/data-science/checkpoint-2.md)
- [Evidence register](docs/data-science/evidence-register.md)

### Web Development documents – `docs/web-dev/`
- [Installation guide](docs/web-dev/installation.md)
- [User guide](docs/web-dev/user-guide.md)
- [API documentation](docs/web-dev/api.md)
- [Database ER diagram](docs/web-dev/er-diagram.md)

### Shared
- [AI-use log](docs/ai-use-log.md)
- GitHub issues are labelled `data-science`, `web-dev` or `shared`.

---

## Features

- Orders with box type, quantity, finishing, material availability and arrival time
- Route checklist per box type: one Start and one Finish button per stage; the machine is
  filled in automatically; each stage can be recorded once; the order completes itself
  after the last stage
- Registration with owner approval; roles *owner* and *manager*
- Full CRUD on orders and stage records; deleting orders is owner-only
- JSON REST API (`/api/v1`)
- Analysis: hypothesis tests, a baseline and two lead-time models with chronological
  validation, robustness checks and figures

## Technology

Python 3.13 · Flask · PostgreSQL 16 · psycopg2 · Bootstrap 5 · pandas · SciPy ·
scikit-learn · matplotlib · pytest · Docker (local database) · Render (web service) ·
Neon (cloud PostgreSQL)

## Quick start

```bash
git clone https://github.com/<your-login>/box-workshop-tracker.git
cd box-workshop-tracker
cp .env.example .env
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
docker compose up -d
docker compose exec -T db psql -U workshop -d workshop_db < db/schema.sql
docker compose exec -T db psql -U workshop -d workshop_db < db/reference_data.sql
.venv/Scripts/python.exe -m flask --app run create-user admin --role owner --password "choose-a-password"
.venv/Scripts/python.exe run.py
```

Open http://127.0.0.1:5000. Full instructions, including cloud deployment:
[installation guide](docs/web-dev/installation.md).

## Tests

```bash
.venv/Scripts/python.exe -m pytest -v
```

Tests use a separate database (`workshop_test`) rebuilt before every test; all records in
tests are synthetic fixtures.

## Analysis

```bash
.venv/Scripts/python.exe -m analysis.run --synthetic 60   # synthetic data, only to test the code
DATABASE_URL="<cloud connection string>" .venv/Scripts/python.exe -m analysis.run   # collected data
```

The report and figures are written to `analysis_output/`.

## Project structure

```
app/            Flask application: pages, API, login, security, shared services
analysis/       Data analysis pipeline (Data Science)
db/             Schema, reference data, stakeholder queries
tests/          Automated tests
docs/           Documentation, split by module
```

## Data and privacy

No personal data about workers is stored (only the number of operators per stage). Client
names, prices and salaries are not collected. Secrets are kept in environment variables
and never committed.
