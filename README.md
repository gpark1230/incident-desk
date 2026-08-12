# IncidentDesk

[![CI](https://github.com/gpark1230/incident-desk/actions/workflows/ci.yml/badge.svg)](https://github.com/gpark1230/incident-desk/actions/workflows/ci.yml)

A backend REST API for tracking and managing security/IT incidents — think a minimal version of the incident-tracking tools SOC/IT teams use daily, built from the engineering side rather than the analyst side.

**Live demo:** https://api-production-1570.up.railway.app — pre-loaded with realistic sample incidents (varied severity/status, comments, full audit trails) so it's not an empty screen on first visit.

**API docs:** https://api-production-1570.up.railway.app/docs

**Try it as a viewer:** sign up for your own free account — new signups are always read-only `viewer` accounts by design (see [`DECISIONS.md`](./DECISIONS.md) for why), so you can browse incidents, comments, and audit trails immediately.

**Try it as an analyst/admin:** to test creating incidents, commenting, or changing status, log in with a shared demo account instead of your own:
- `demo.analyst@incidentdesk.dev` / `Demo2026Pass!`
- `demo.admin@incidentdesk.dev` / `Demo2026Pass!`

These are demo-only credentials on synthetic data — nothing sensitive, feel free to create/edit incidents to try it out. Data may be periodically reset.

## Why this exists

I work as an IT Operations and Security Associate, where a large part of my day is triaging alerts (CrowdStrike, ticketing systems), documenting incidents, and tracking who did what and when for compliance purposes. I built IncidentDesk to work through the same problem from the other side of the tool — designing the data model, the authorization rules, and the audit trail that make that kind of system trustworthy, instead of just using one.

It's deliberately not a generic CRUD/todo app: it has real relational complexity (incidents → comments, incidents → audit log), real authorization logic beyond "logged in or not," and an append-only audit trail modeled on real SOC/compliance tooling patterns.

Every non-obvious engineering decision made while building this — including a couple of real bugs hit and fixed along the way — is written up in [`DECISIONS.md`](./DECISIONS.md).

## Features

- **A real minimal frontend** — login/signup, a filterable incident dashboard, and a detail view with comments and the full audit trail (plain HTML/CSS/JS, no framework — see [`DECISIONS.md`](./DECISIONS.md) for why)
- **JWT authentication** — signup, login, bcrypt password hashing
- **Role-based access control** — `viewer` (read-only), `analyst` (create/update incidents and comments), `admin` (full control)
- **Incident management** — create, read, filter, and update incidents (severity, status, assignment)
- **Comments** — threaded notes on an incident, one-to-many
- **Append-only audit log** — every incident creation, field change, and comment is recorded with who/what/when; nothing in the API can edit or delete an audit entry
- **Filtering & pagination** on the incident list — by status, severity, assignee, and date range
- **Redis event stream** — incident create/update/comment actions publish a small JSON event to a Redis list, best-effort (the API keeps working fine if Redis is down — see [`DECISIONS.md`](./DECISIONS.md))
- **19 automated tests** covering auth, RBAC enforcement, and incident/audit-log behavior, run against a real Postgres test database
- **Alembic migrations** — schema changes are versioned, not a `create_all()` guess
- **Dockerized**, with a `docker-compose.yml` that runs the full stack (API + Postgres + Redis) with one command
- **CI/CD** — GitHub Actions runs the full test suite and a Docker build check on every push; Railway auto-deploys `main` on every push (not currently gated on CI passing — see [`DECISIONS.md`](./DECISIONS.md))

## Tech stack

- **FastAPI** — routing, request validation, auto-generated OpenAPI docs
- **PostgreSQL** + **SQLAlchemy ORM** — data layer
- **Alembic** — database migrations
- **JWT** (`python-jose`) + **bcrypt** — authentication
- **pytest** — test suite
- **Docker** + **GitHub Actions** — containerized, tested and built on every push

## Sample request/response

Every incident change is captured automatically — here's what closing an incident looks like from the audit trail:

```
$ curl -X PATCH https://api-production-1570.up.railway.app/incidents/3 \
    -H "Authorization: Bearer <analyst-or-admin-token>" \
    -H "Content-Type: application/json" \
    -d '{"status": "closed"}'

{
  "id": 3,
  "title": "Ransomware alert from CrowdStrike",
  "severity": "critical",
  "status": "closed",
  "assigned_to_id": 3,
  "created_by_id": 3,
  "created_at": "2026-08-12T11:25:56.302188-04:00",
  "updated_at": "2026-08-12T11:25:56.358562-04:00"
}

$ curl https://api-production-1570.up.railway.app/incidents/3/audit-log \
    -H "Authorization: Bearer <any-authenticated-token>"

[
  { "action": "created", "details": "severity: critical", ... },
  { "action": "updated", "details": "status: open -> closed; assigned_to_id: None -> 3", ... }
]
```

Full interactive API docs (Swagger UI) are available at `/docs` on any running instance.

## Running it locally

### Option A: Docker Compose (fastest — no local Python/Postgres needed)

```bash
git clone https://github.com/gpark1230/incident-desk.git
cd incident-desk
docker compose up
```

That's it — API + Postgres both running, migrations applied automatically on
boot. Open **http://localhost:8000/docs**.

### Option B: Plain Python + local Postgres

**Prerequisites:** Python 3.11+, PostgreSQL running locally.

```bash
git clone https://github.com/gpark1230/incident-desk.git
cd incident-desk

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

createdb incident_desk
cp .env.example .env   # then edit DATABASE_URL / SECRET_KEY as needed

alembic upgrade head

uvicorn app.main:app --reload
```

Then open **http://localhost:8000/docs** for the interactive API explorer.

## Database migrations

Schema is managed by Alembic, not a `create_all()` guess. To change the schema:
edit `app/models.py`, then `alembic revision --autogenerate -m "description"`,
review the generated file in `alembic/versions/`, then `alembic upgrade head`.

## Running the tests

Tests run against a second, real Postgres database (not mocks or SQLite — the app relies on real Postgres `Enum` behavior for role/severity/status).

```bash
createdb incident_desk_test
python -m pytest tests/ -v
```

## API overview

| Method | Route | Access |
|---|---|---|
| `POST` | `/auth/signup` | Public (always creates a `viewer`) |
| `POST` | `/auth/login` | Public |
| `GET` | `/auth/me` | Any authenticated user |
| `GET` | `/incidents` | Any authenticated user (filterable, paginated) |
| `POST` | `/incidents` | `analyst`, `admin` |
| `GET` | `/incidents/{id}` | Any authenticated user |
| `PATCH` | `/incidents/{id}` | `analyst`, `admin` |
| `GET` | `/incidents/{id}/comments` | Any authenticated user |
| `POST` | `/incidents/{id}/comments` | `analyst`, `admin` |
| `GET` | `/incidents/{id}/audit-log` | Any authenticated user |
