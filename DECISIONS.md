# IncidentDesk — Decision Log

Running log of real engineering decisions made on this project, with the reasoning
behind each one. Kept for two reasons: (1) so Gavin can explain *why* the code looks
the way it does in interviews, not just *what* it does, and (2) as a build record
alongside the git history.

Format per entry: what was decided, why, what else was considered, and anything
worth remembering if asked about it in an interview.

---

## 2026-08-12 — Config loading via `python-dotenv` + `os.environ[...]`

**Decision:** `app/config.py` loads `.env` with `python-dotenv`, then reads
`DATABASE_URL` and `SECRET_KEY` with `os.environ["..."]` (not `.get()`).

**Why:** Using `os.environ[...]` (square brackets) instead of `os.environ.get(...)`
means the app crashes immediately at startup if a required env var is missing,
instead of silently running with `None` and failing weirdly later, e.g. deep inside
a JWT-signing call with `SECRET_KEY=None`. Fail loud and early at boot, not late and
confusing at request time.

**Alternatives considered:** `pydantic-settings` (a `BaseSettings` class) is the more
"proper" FastAPI-idiomatic way to manage config, and validates types automatically.
Skipped for now to keep the setup phase simple and avoid an abstraction that isn't
pulling its weight yet at two config values. Worth revisiting if the config surface
grows (e.g. adding token expiry settings, CORS origins, etc.).

**Interview point:** Can explain the difference between failing fast at startup vs.
failing late at request time, and why that matters for debugging production issues.

---

## 2026-08-12 — Database session pattern: `SessionLocal` + `get_db()` generator

**Decision:** `app/database.py` defines `engine`, `SessionLocal` (a session factory),
and a `get_db()` generator function that yields a session and closes it in a
`finally` block.

**Why:** This is the standard FastAPI dependency-injection pattern for database
access. Each incoming request gets its own DB session (not a shared global one —
that would cause cross-request bugs under concurrency), and `yield` + `finally`
guarantees the session is closed even if the route raises an exception. Routes will
declare `db: Session = Depends(get_db)` and FastAPI runs this function around the
request automatically.

**Alternatives considered:** A single module-level session shared across requests —
rejected immediately, this breaks under any concurrent traffic and is a well-known
anti-pattern. Async SQLAlchemy (`asyncpg` + async sessions) — skipped for now
because psycopg2 (sync) is simpler to reason about and debug while still learning
the ORM; async adds real complexity (async engine, async session, `await` on every
query) that isn't worth it yet at this scale.

**Interview point:** Can explain *why* a new session per request matters — it's a
concurrency/isolation question, not just a style preference.

---

## 2026-08-12 — Models in one `app/models.py` file, not a `models/` package

**Decision:** `User`, `Incident`, `Comment`, and `AuditLog` all live in a single
`app/models.py`, rather than one file per model in a `models/` directory.

**Why:** At four related, small models, splitting into separate files adds import
overhead (circular-import risk between `Incident` and `Comment`, since they reference
each other) without a real organizational win. One file is easier to read top-to-
bottom and easier to explain in an interview.

**Alternatives considered:** `app/models/user.py`, `app/models/incident.py`, etc.
This is the more common pattern in larger production codebases and is worth
switching to if the model count grows significantly. Noted here so it's a deliberate
choice, not an oversight, if asked "why isn't this split up?"

---

## 2026-08-12 — Roles, severity, and status as Python `enum` + SQLAlchemy `Enum`

**Decision:** `UserRole`, `Severity`, and `IncidentStatus` are Python `enum.Enum`
classes (subclassing `str`), mapped to Postgres via SQLAlchemy's `Enum` column type.

**Why:** This pushes validation down to the database itself — Postgres will reject
an insert with `role = "superadmin"` at the DB level, not just in application code.
It also gives autocomplete/type-checking in Python and makes the valid states
self-documenting directly in the model instead of scattered in comments or docs.

**Alternatives considered:** Plain `String` columns with validation only in FastAPI
request schemas (Pydantic) — simpler, but means the database itself has no opinion
about what's valid, so a bad value written via a raw SQL script or another tool
would go in silently. Enum was chosen deliberately as the "belt and suspenders"
approach, consistent with treating this as a compliance-adjacent tool.

**Interview point:** Can explain defense-in-depth — validating at both the API layer
(Pydantic) and the data layer (DB enum), not trusting the application layer alone.

---

## 2026-08-12 — Two foreign keys from `Incident` to `users`, with explicit `foreign_keys=[...]`

**Decision:** `Incident` has both `created_by_id` and `assigned_to_id`, each a
foreign key to `users.id`, with two separate `relationship()` calls that each
specify `foreign_keys=[...]` explicitly.

**Why:** An incident needs to track who opened it *and* who currently owns it, and
those are frequently different people. SQLAlchemy can usually infer which FK column
a relationship should use automatically — but when there are *two* FKs from the same
table to the same target table, it can't guess which is which, so it has to be told
explicitly or it raises an `AmbiguousForeignKeysError`.

**Alternatives considered:** None seriously — this is the standard way to model
"two different relationships to the same table" in SQLAlchemy. Documented here
mainly because it's a common real gotcha worth being able to explain if someone
reads the model and asks "why is `foreign_keys=` needed here specifically?"

---

## 2026-08-12 — Audit log is append-only by omission, not by DB constraint

**Decision:** `AuditLog` has no update or delete path anywhere in the (planned) API.
There is currently no database-level trigger or permission that would physically
block an `UPDATE`/`DELETE` on the `audit_logs` table — the guarantee is "the code
never exposes a route to do it," not "the database refuses to allow it."

**Why:** This is the honest, current state of the implementation as of this
milestone. It's a deliberate placeholder, not a finished guarantee — worth being
upfront about rather than overstating "tamper-proof" in the README or in an
interview.

**Possible future hardening (not yet built):** a Postgres `REVOKE UPDATE, DELETE`
on that table for the app's DB role, or a trigger that rejects any `UPDATE`/`DELETE`
on `audit_logs` outright, would make this a real DB-level guarantee instead of an
application-layer convention.

**Interview point:** Be ready to answer "how do you know no one can tamper with the
audit log?" honestly: right now, they'd have to bypass the API and talk to Postgres
directly with valid credentials — the app-layer guarantee is real, but the DB-layer
guarantee isn't built yet. That's a good answer; overclaiming it is not.

---
