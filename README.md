# Box Workshop Production Tracker

A data-collection and analysis system for a small corrugated box workshop.
The workshop manager records orders and production stages through a web form;
records are validated and stored in PostgreSQL with time and source information.
The collected data will be used to identify production bottlenecks and to predict
order lead time.

Module: UDE5014CM Data Science for Developers — Assessment 2
Current stage: **Checkpoint 1 – Data collection MVP**

## Requirements

- Python 3.12 or 3.13
- Docker Desktop (running)
- Git

## 1. Setup

```bash
git clone https://github.com/botu0106/box-workshop-tracker.git
cd box-workshop-tracker
cp .env.example .env
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (Git Bash)
source .venv/Scripts/activate
# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 2. Initialise the database

```bash
docker compose up -d
```

Wait about 5 seconds for PostgreSQL to start, then create the tables and reference data:

```bash
docker compose exec -T db psql -U workshop -d workshop_db < db/schema.sql
docker compose exec -T db psql -U workshop -d workshop_db < db/reference_data.sql
```

Check that the tables exist:

```bash
docker compose exec db psql -U workshop -d workshop_db -c "\dt"
```

To reset the database completely (deletes all data): `docker compose down -v`, then repeat this section.

## 2b. Create a user

All data pages require login. Create a user (choose your own password):

```bash
python -m flask --app run create-user manager --password "choose-a-password"
```

## 3. Run the application

```bash
python run.py
```

Open http://127.0.0.1:5000

## 4. Run the tests

```bash
python -m pytest -v
```

The tests use a separate database (`workshop_test`) that is rebuilt before every test.
All records created in tests are synthetic test fixtures and never touch the collected data.

## 5. Demonstration: create and retrieve a new record

1. Open http://127.0.0.1:5000/orders/new and save a new order.
2. The order appears on the **Orders** page.
3. Click the order number to open the order page and press **+ Add stage**.
4. Record a stage (e.g. *Corrugated board cutting*) and save.
5. The stage appears on the order page together with its provenance:
   who entered it, when it was entered, and whether it was recorded in real time or later.
6. Try invalid input (finish time before start time, more defects than boxes,
   a machine that does not fit the stage): the record is rejected with a clear message.

## Project structure

```
app/            Flask application (routes, validation, templates)
db/             SQL schema and reference data
tests/          Unit and integration tests
docs/           Checkpoint documentation, evidence register, AI-use log
```

## Data and privacy

- No personal data about workers is collected (only the number of operators per stage).
- No client names, prices or salaries are stored.
- Secrets are kept in `.env`, which is excluded from version control.

## Documentation

- [Checkpoint 1](docs/checkpoint-1.md)
- [Evidence register](docs/evidence-register.md)
- [AI-use log](docs/ai-use-log.md)