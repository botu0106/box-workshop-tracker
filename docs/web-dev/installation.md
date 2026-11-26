# Installation guide

Two ways to run the application: **locally** with a PostgreSQL database in Docker, or
**in the cloud** on Render with a Neon database (how the live application runs).

## 1. Local installation

### Requirements

- Python 3.12 or 3.13
- Docker Desktop (running)
- Git

### Steps

```bash
git clone https://github.com/<your-login>/box-workshop-tracker.git
cd box-workshop-tracker
cp .env.example .env            # then set your own POSTGRES_PASSWORD and SECRET_KEY
python -m venv .venv
```

Install the dependencies (Windows paths; on macOS/Linux use `.venv/bin/python`):

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Start the database and create the tables and reference data:

```bash
docker compose up -d
# wait about 5 seconds for PostgreSQL to start
docker compose exec -T db psql -U workshop -d workshop_db < db/schema.sql
docker compose exec -T db psql -U workshop -d workshop_db < db/reference_data.sql
```

Both scripts are safe to run again: they only create what is missing and never delete data.

Create the first user (the owner):

```bash
.venv/Scripts/python.exe -m flask --app run create-user admin --role owner --password "choose-a-password"
```

Run the application:

```bash
.venv/Scripts/python.exe run.py
```

Open http://127.0.0.1:5000 and log in.

### Run the tests

```bash
.venv/Scripts/python.exe -m pytest -v
```

The database container must be running. Tests create and rebuild their own database,
`workshop_test`, so the development data is not touched.

## 2. Cloud deployment (Render + Neon)

### Database – Neon

1. Create a project at neon.com (PostgreSQL 16, region close to the users, e.g. Frankfurt).
2. In the **SQL Editor**, run the whole of `db/schema.sql`, then `db/reference_data.sql`.
3. Set the workshop time zone:
   ```sql
   ALTER DATABASE neondb SET timezone TO 'Asia/Tashkent';
   ```
4. **Connect** → turn **Connection pooling off** → copy the connection string
   (it ends with `?sslmode=require`, so the connection is encrypted).

### Web service – Render

1. **New → Web Service**, connect the GitHub repository, branch `main`.
2. Settings:

   | Setting | Value |
   |---|---|
   | Language | Python 3 |
   | Build command | `pip install -r requirements.txt` |
   | Start command | `gunicorn "app:create_app()"` |
   | Health check path | `/health` |

3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `SECRET_KEY` | a random value: `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `APP_ENV` | `production` |
   | `PYTHON_VERSION` | e.g. `3.13.1` |

4. Deploy. Render serves the application over HTTPS and redeploys on every push to `main`.

### First user in the cloud database

Run once from your computer, pointing the command at the cloud database:

```bash
DATABASE_URL="<Neon connection string>" .venv/Scripts/python.exe -m flask --app run create-user admin --role owner --password "choose-a-password"
```

Other people register on the site and the owner approves them on the **Foydalanuvchilar** page.

### Updating the schema later

Schema changes are written as `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so the same
`db/schema.sql` can be run again on the existing cloud database. Run it in the Neon SQL Editor
**before** pushing code that uses the new columns.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `Connection refused` on port 5433 | The Docker database is not running: start Docker Desktop and `docker compose up -d`. |
| `relation "..." does not exist` | The schema was not loaded into this database: run `db/schema.sql`. |
| `column "..." does not exist` on Render | The cloud database was not updated: run `db/schema.sql` in Neon. |
| The site takes about a minute to open | The free Render service sleeps after 15 minutes without visits; the first request wakes it. |
| `SECRET_KEY must be set in production` | Set `SECRET_KEY` in the Render environment variables. |
