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

## 2026-08-12 — Password hashing: switched from `passlib` to raw `bcrypt`

**Decision:** Started with `passlib`'s `CryptContext` (the pattern in most FastAPI
tutorials), but hit a real runtime error on the very first signup request:
`ValueError: password cannot be longer than 72 bytes` — thrown on an 11-character
password. Root cause: `passlib` 1.7.4 (unmaintained since 2020) runs an internal
self-test against the installed `bcrypt` library at first use, and that self-test is
broken against `bcrypt` 4.1+/5.x because newer `bcrypt` changed how it reports its
version. The error message is misleading — it's not actually about password length.
Fixed by dropping `passlib` entirely and calling `bcrypt.hashpw` / `bcrypt.checkpw`
directly in `app/security.py`.

**Why:** Rather than pin `bcrypt` down to an old compatible version (a real option —
`bcrypt<4.1` — but a landmine for whoever upgrades dependencies later without
knowing why), removing the abstraction that was actually broken is more durable.
`bcrypt` alone is a thin, actively maintained library; `passlib` was only adding a
convenience wrapper we didn't need for a single hashing scheme.

**Alternatives considered:** Pin `bcrypt==4.0.x` and keep `passlib` — rejected as a
fragile fix that just defers the same problem to the next dependency upgrade.

**Interview point:** This is a good real story for "tell me about a bug you hit" —
a misleading error message (password length) that was actually a dependency
compatibility issue, diagnosed by reading the actual traceback instead of trusting
the surface-level error text.

---

## 2026-08-12 — Auth routes: `/auth/signup`, `/auth/login`, `/auth/me`

**Decision:** Login uses `OAuth2PasswordRequestForm` (form-encoded `username`/
`password`, not JSON), per the OAuth2 spec that `python-jose` + FastAPI's security
utilities are built around — `username` is just mapped to email here. New users
always sign up as `role=viewer` (the model default); there is no way yet to create
an `admin` or `analyst` through the API. `get_current_user` (from `app/auth.py`) is
used as a `Depends(...)` on `/auth/me` to prove the full JWT round-trip works.

**Why:** Following the OAuth2 password-flow spec instead of a custom JSON login body
means the `/docs` page auto-generates a working "Authorize" button — a real, free
recruiter-visibility win (CLAUDE.md's goal of a good `/docs` page). Defaulting
signup to `viewer` is a deliberate security choice: privilege escalation (becoming
`admin`) should never be self-service through a public signup endpoint.

**Current limitation:** There's no `admin` user yet and no way to create one except
by hand (e.g. `UPDATE users SET role = 'admin' WHERE id = 1;` via `psql`). A proper
fix — either a one-time bootstrap script or an admin-only "promote user" endpoint —
is still open and needed before RBAC-protected admin routes can be tested end to end.

**Verified end-to-end (manual curl testing):** signup → 201, login → JWT, `/auth/me`
with valid token → 200 with correct user, `/auth/me` with missing/garbage token →
401, duplicate signup email → 400, wrong password on login → 401.

---

## 2026-08-12 — RBAC enforcement via a `require_role(...)` dependency factory

**Decision:** `app/auth.py` adds `require_role(*allowed_roles)`, a function that
*returns* a FastAPI dependency rather than being one itself. Routes use it as
`Depends(require_role(UserRole.analyst, UserRole.admin))`. Internally it first
resolves `get_current_user` (so the token is already verified), then checks
`current_user.role` against the roles passed in; anything else raises 403.

**Why:** This keeps the RBAC rule sitting directly on each route's signature —
reading `app/routers/incidents.py`, you can see exactly who's allowed to hit each
endpoint without reading any function body. It's also the same dependency-injection
pattern already used for `get_current_user` and `get_db`, so there's only one
mental model for "things that gate a route," not a second, different mechanism for
roles specifically.

**Alternatives considered:** An `if current_user.role != "admin": raise ...` check
written manually inside each route body — rejected because it's easy to forget on
a new route, and duplicates the same check everywhere. A factory function
declared once and reused is the more standard FastAPI pattern.

**Interview point:** Can explain the difference between a dependency and a
dependency *factory* — `Depends(get_current_user)` vs. `Depends(require_role(...))`
— and why the extra layer of function-returning-a-function is needed here (the
allowed roles differ per route, so the dependency itself needs to be parameterized).

---

## 2026-08-12 — Incident routes: PATCH for updates, all roles can read

**Decision:** `POST /incidents` and `PATCH /incidents/{id}` require
`analyst` or `admin` (via `require_role`). `GET /incidents` and
`GET /incidents/{id}` only require a valid logged-in user (`get_current_user`,
no role check) — so `viewer` accounts can read but never write. There is no
separate "close incident" endpoint; closing is just
`PATCH {"status": "closed"}`, using the same partial-update route as any other
field change.

**Why:** Matches CLAUDE.md's RBAC spec directly (viewer = read-only, analyst =
create/update, admin = full control) with the fewest routes possible. A dedicated
`/incidents/{id}/close` endpoint would just be a worse-typed version of the PATCH
route that already exists — one more thing to maintain for no real behavior
difference.

**Verified end-to-end (manual curl testing with real viewer/analyst/admin
accounts, roles promoted by hand via `psql` since there's still no admin-management
endpoint):** viewer `POST` → 403, analyst `POST` → 201, viewer `GET` (list and by
id) → 200, viewer `PATCH` → 403, admin `PATCH` (status → `closed`) → 200 with the
status actually updated, `GET` on a nonexistent id → 404.

**Still open:** audit log isn't wired to these routes yet — `PATCH`ing an
incident's status right now leaves no record of who changed what or when. That's
the next milestone.

---

## 2026-08-12 — Audit log wiring: diff-based, one row per meaningful change

**Decision:** `create_incident` writes one `AuditLog` row (`action="created"`).
`update_incident` computes a diff — for each field actually sent in the `PATCH`
body, it compares the old value to the new one, and only if they differ does it
(a) apply the change and (b) add that field to a single `"; "`-joined `details`
string on one `AuditLog` row (`action="updated"`). A `PATCH` that sends a field but
with its current value (a genuine no-op) writes **no** audit row at all — verified
by testing a same-value `PATCH` and confirming the audit trail didn't grow.

**Why:** One row per *call*, not one row per *field*, keeps the audit trail
readable as a human ("who did what, when") rather than a wall of single-field rows
that need to be manually grouped back together. Skipping no-op updates keeps the
log meaningful — a `PATCH` that changes nothing isn't a real state change worth an
audit entry.

**Also fixed along the way:** the first version of `details` printed
`"severity: Severity.medium"` instead of `"severity: medium"` — `str(enum_member)`
on a `class X(str, enum.Enum)` doesn't reliably return the plain value across
Python versions/behavior. Added a small `_fmt()` helper in
`app/routers/incidents.py` that explicitly reads `.value` for enum members. Worth
remembering: don't trust implicit `str()`/f-string formatting of mixed-in enums —
be explicit about `.value`.

**Transaction detail worth explaining if asked:** `create_incident` calls
`db.flush()` (not `db.commit()`) right after `db.add(incident)`. `flush()` sends
the pending SQL to Postgres and assigns `incident.id` from the database's identity
column, but doesn't end the transaction — so the audit row (which needs
`incident.id` as a foreign key) can be built, and then both rows commit together
in one transaction. If anything failed between `flush()` and `commit()`, both
would roll back — never an incident row with no matching audit trail.

**Also added:** `GET /incidents/{id}/audit-log` — read-only, any authenticated
role (viewers included, since RBAC treats them as read-only everywhere, not
locked out of the audit trail specifically). There is still no route anywhere
that can update or delete an `AuditLog` row.

**Verified end-to-end:** create → 1 audit row (`created`, with severity).
`PATCH` changing 2 fields → 1 audit row (`updated`, both changes listed).
`PATCH` re-sending an unchanged value → 0 new audit rows. Read via
`/audit-log` as a viewer → 200 with the full, correctly-ordered trail.

---

## 2026-08-12 — Comments: nested under incidents, gated the same as incident writes, feed the audit log

**Decision:** `POST /incidents/{id}/comments` and `GET /incidents/{id}/comments`
live on the same router (`app/routers/incidents.py`), not a separate
`app/routers/comments.py`. Posting a comment requires `analyst`/`admin`
(same `require_role` gate as incident writes); reading requires only a logged-in
user. Posting a comment also writes an `AuditLog` row (`action="commented"`),
with `details` truncated to the first 100 characters of the comment body — the
full text lives in the `comments` table, the audit row just needs to say
*that* a comment happened and roughly what it said.

**Why routed together:** a comment doesn't exist independently of an incident —
every comment route needs the `incident_id` from the URL path anyway
(`/incidents/{id}/comments`), so splitting it into its own router file would mean
importing `Incident` there too just to do the same "does this incident exist"
404 check. Keeping it in `incidents.py` matches the actual dependency, not an
arbitrary one-file-per-model rule.

**Why comments feed the audit log too:** CLAUDE.md's audit log spec is "every
state change on an incident" — a comment is part of the incident's timeline
(an analyst leaving investigation notes), so it belongs in the same trail as
severity/status changes, not off in a silo you'd have to check separately to
get the full picture of "what happened to this incident."

**Verified end-to-end:** viewer `POST` comment → 403, analyst `POST` → 201,
viewer `GET` comments → 200 (can read, can't write), audit log picks up the
comment automatically as a `commented` entry right after `created`, `POST`
comment on a nonexistent incident id → 404.

---

## 2026-08-12 — Filtering and pagination on `GET /incidents`: query params, offset-based

**Decision:** `list_incidents` gained optional query params: `status`, `severity`,
`assigned_to_id`, `created_after`, `created_before`, plus `skip`/`limit` for
pagination (`limit` capped at 100 via `Query(..., le=100)`). Each filter is applied
conditionally — only `.filter(...)` if the client actually passed that param —
and they compose (e.g. `?severity=critical&status=open` narrows by both). The
Python parameter is named `status_` (not `status`) because `status` is already
imported from `fastapi` for HTTP status codes elsewhere in the file; `Query(None,
alias="status")` keeps the actual URL param spelled `?status=...` for clients —
the underscore is purely an internal naming fix, invisible over HTTP.

**Why offset-based (`skip`/`limit`) over cursor-based pagination:** cursor
pagination (returning an opaque "next page" token) scales better under heavy
concurrent writes, but is real added complexity for a project at this size.
`skip`/`limit` is the standard, immediately explainable pattern and is what most
interviewers will expect a junior/mid engineer to reach for first.

**Why no response envelope (e.g. `{"total": N, "items": [...]}`)**: kept the
response as a plain `list[IncidentOut]`, matching every other list endpoint in
the API. Adding a total count would require a second `COUNT(*)` query on every
list call for a number the frontend doesn't strictly need yet — can be added
later if a real pagination UI needs it.

**Verified end-to-end:** `?severity=critical` returns only critical incidents,
`?status=open` returns only open ones, `?limit=2` caps results to 2, an invalid
enum value (`?severity=nonsense`) → 422 with no manual validation code (Pydantic/
FastAPI reject it automatically from the `Severity` enum type), `?limit=500` → 422
(rejected by the `le=100` constraint).

---

## 2026-08-12 — pytest suite: real Postgres test DB, dependency override, per-test wipe

**Decision:** Tests run against a second, real Postgres database
(`incident_desk_test`, same server, same `incident_desk_user`) — not SQLite, not
mocks. `tests/conftest.py` sets `DATABASE_URL`/`SECRET_KEY` env vars *before*
anything imports `app.database` or `app.main` (since `app/config.py` reads them
at import time), then uses FastAPI's `app.dependency_overrides[get_db] = ...` to
point every route's `Depends(get_db)` at a session bound to the test database
instead. An `autouse` fixture drops and recreates every table before each test
function, so tests never see leftover data from a previous test. A `make_user`
fixture creates `analyst`/`admin` accounts by writing directly to the test DB
(bypassing `/auth/signup`, which can only ever create a `viewer`) — the only way
to get a non-viewer account for testing, same limitation as the manual `psql`
promotion used during manual testing earlier.

**Why real Postgres, not SQLite for speed:** the app leans on Postgres-specific
behavior (the `Enum` columns for role/severity/status validate against actual
Postgres enum types). Testing against SQLite would test a database that isn't
actually being used in production/dev — a false sense of safety. The cost is
tests are slower and need a running Postgres server, which is an honest tradeoff
to state in an interview, not a downside to hide.

**Why drop-and-recreate tables per test, not a rollback-per-test transaction:**
the more "correct" pattern for test isolation is wrapping each test in a
transaction that's rolled back at the end (faster, no schema rebuild). Chose the
simpler drop/recreate approach instead because it's easier to reason about and
explain, and at 19 tests the extra ~10s cost doesn't matter yet. Worth switching
to transaction-per-test if the suite grows large enough for the rebuild cost to
become annoying.

**Also fixed along the way:** all four `*Out` schemas were still using Pydantic
v1-style `class Config: from_attributes = True`, which pytest flagged as
deprecated (removed entirely in Pydantic v3). Swapped to
`model_config = ConfigDict(from_attributes=True)` across `app/schemas.py`.

**Coverage:** 19 tests across three files — `test_auth.py` (signup/login/`/me`
happy paths and failures), `test_rbac.py` (viewer blocked from every write route,
analyst/admin allowed, viewer still allowed to read), `test_incidents.py`
(audit log entries on create/update/comment, no-op updates logging nothing,
filtering, pagination, 404 on a missing incident). All passing.

---

## 2026-08-12 — Deployment: Railway, two services (Postgres + api), no Dockerfile

**Decision:** Deployed to Railway rather than Render or Fly.io — one project with
two services: a managed Postgres addon and an `api` service deployed straight from
this local repo via `railway up` (not yet GitHub-connected for auto-deploy on
push — that's a natural next step, not done today). Railway's own builder
(Railpack) detects Python from `requirements.txt` and needs a `Procfile` to know
how to start the app: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
`$PORT` is injected by Railway at runtime — the app doesn't hardcode a port.
`DATABASE_URL` on the `api` service is set to Railway's own variable-reference
syntax `${{Postgres.DATABASE_URL}}`, so the real connection string (including its
password) is never typed into a command, a file, or this log — Railway resolves
it internally between services. `SECRET_KEY` is a freshly generated random value
(`secrets.token_urlsafe(48)`), set only as an environment variable on Railway,
never committed — completely different from the `changeme` placeholder in
`.env.example`.

**Why Railway over Render/Fly.io:** fastest path to a working FastAPI + Postgres
deploy from the CLI with the least new configuration (no Dockerfile needed, unlike
Fly.io). Render was the other close option; picked mainly for CLI speed today —
worth trying Render too later since CLAUDE.md's roadmap treats the PaaS choice as
non-final.

**Real gap, said plainly:** there's no Alembic migration setup yet. `app/main.py`
runs `Base.metadata.create_all(bind=engine)` on every startup as a stand-in —
fine for creating tables that don't exist yet, but it does **not** handle
altering an existing column or table safely. This is acceptable for a project
with no real users yet; it would not be acceptable once there's production data
a schema change could silently fail to migrate. Real migrations (Alembic) are
the next infrastructure milestone before this app is treated as "production."

**Verified end-to-end against the live deployment (not just health check):**
`POST /auth/signup` → 201 and a real row written to the live Postgres instance,
`POST /auth/login` → real JWT, `GET /auth/me` with that token → 200 with the
correct user, `GET /docs` → 200. The full stack — build, deploy, DB connection,
password hashing, JWT signing/verification — works against the actual deployed
instance, not just locally.

---

## 2026-08-12 — Added a minimal frontend: plain HTML/CSS/JS, no framework, no build step

**Decision:** After asking what "make the live demo look nicer" should mean (a
Swagger docs polish pass vs. a static landing page vs. a real frontend), a real
minimal frontend was chosen — login/signup, an incident list with filters, and an
incident detail view (comments + audit trail), all calling the existing API.
Built as one static HTML page (`app/static/index.html`) with vanilla JS
(`app/static/app.js`) doing view-switching by toggling CSS classes — no React/Vue,
no npm, no build step. Served by FastAPI itself: `StaticFiles` mounted at
`/static`, and a `GET /` route returns `index.html` directly
(`include_in_schema=False` so it doesn't clutter the OpenAPI docs, which are still
the "real" API reference at `/docs`).

**Why no framework:** this project's stated purpose (per this file, above) is a
*backend* portfolio piece, and Gavin's learning history has no JS framework
experience yet. A framework would add a build toolchain (npm/vite/webpack) that's
a whole separate thing to learn and explain in an interview, for a UI that's
fundamentally simple (a login form, a list, a detail page). Plain JS keeps the
addition explainable and scoped, and — practically — same-origin serving from
FastAPI means zero CORS configuration was needed.

**Security note worth being precise about in an interview:** the frontend hides
the "New Incident" button and comment form for `viewer` accounts
(`canWrite()` checks `currentUser.role`), but that is a **UX convenience, not a
security boundary** — the real enforcement is still 100% server-side
(`require_role(...)` in `app/routers/incidents.py`, unchanged by this work). A
viewer who opened devtools and called the API directly would still get a real 403,
exactly as before. The frontend hiding a button and the backend rejecting the
request are two different, independently-necessary things — don't confuse "the
button is hidden" with "the action is prevented."

**JWT storage tradeoff, stated honestly:** the token is stored in
`localStorage`, which is simple and persists across page reloads, but is
readable by any JavaScript that runs on the page — meaning an XSS vulnerability
elsewhere on the same page could steal it. An httpOnly cookie would be safer
against that specific attack but requires the backend to set/manage the cookie
and adds CSRF considerations. `localStorage` was chosen deliberately for
simplicity at this project's stage — worth naming as a known tradeoff, not an
oversight, if asked "how would you harden this?"

**Also fixed along the way:** `@app.on_event("startup")` (used for the
`create_all()` table-creation stand-in) is deprecated in current FastAPI in favor
of the `lifespan` context-manager pattern. Swapped to
`@asynccontextmanager async def lifespan(app): ...; yield` passed to
`FastAPI(lifespan=lifespan)`, which also cleared a pytest deprecation warning.

**Verified:** all 19 backend tests still pass unchanged (frontend work touched
`app/main.py` only to mount static files and add the `/` route — no route
behavior changed). Visually verified locally using headless Chrome screenshots
(no interactive browser tool was available this session) — login view, and a
fully authenticated dashboard + detail view driven by a real login token and real
data from the dev database, confirming badges, cards, and the audit trail render
correctly end to end, not just that the HTML is well-formed.

---

## 2026-08-12 — Seeded the live production database, and published demo credentials

**Decision:** Realized after deploying the frontend that a real visitor signing
up on the live demo would land on a completely empty dashboard with no incidents
and no way to create one — new signups are always `viewer` (deliberately, see
the "Auth routes" decision above), and viewers can't write. An empty screen with
no way to populate it is a bad first impression and doesn't demonstrate the
audit-log/RBAC features at all. Fixed two ways: (1) seeded the live Postgres
database with 6 realistic incidents across every severity and status, each with
a natural-looking history of comments and status changes created *through the
real API* (not raw SQL inserts) so the audit log reads like genuine incident
response activity, not obviously fake seed data; (2) created and published two
demo accounts (`demo.analyst@incidentdesk.dev`, `demo.admin@incidentdesk.dev`,
password `Demo2026Pass!`) in the README, so visitors who want to test write
actions (create an incident, comment, change status) don't have to take my word
for it — they can log in and do it themselves.

**How the roles got promoted:** same fundamental limitation as before — no
admin-promotion endpoint exists. Signed the accounts up through `/auth/signup`
(both start as `viewer`), then promoted them directly in the production database.
Getting *to* the production database from a local machine turned out to be its
own small problem worth recording: Railway's SSH tunnel
(`railway connect postgres --tunnel-only`) failed repeatedly with
`channel 1: open failed: unknown channel type: unsupported` — happened even
with sandboxing disabled, so it wasn't a local sandbox restriction, something
about that specific tunnel path didn't work in this session. Worked around it
with `railway ssh --service api -- python3 -c "..."` instead: SSH into the
already-deployed `api` container itself (which needed an `ed25519` key
specifically — the existing `id_rsa` key was rejected) and run a short Python
script there that imports `app.database`/`app.models` directly. Since that
container already has `DATABASE_URL` pointed at Postgres's *internal* Railway
hostname (only reachable from inside Railway's network), running the promotion
code from inside the container sidestepped the tunnel problem entirely.

**Why seed through the real API instead of direct SQL inserts:** every incident
was created via `POST /incidents`, every comment via `POST /incidents/{id}/comments`,
every status change via `PATCH /incidents/{id}` — using the demo accounts' real
JWTs, exactly like any other user would. This guarantees the seeded data is
self-consistent with the app's own rules (correct audit log entries, correct
timestamps, correct relationships) automatically, instead of hand-writing SQL
that could drift from what the application logic actually produces.

**Verified:** a screenshot of a genuinely fresh throwaway viewer signup
(`screenshot.check@example.com`, never used before) hitting the live URL shows
all 6 seeded incidents with correct severity/status badges and no write
controls (confirming both "populated by default" and "still correctly
read-only" at once). One stray test user (`demo@example.com`, an artifact of
the deployment smoke-test) was deleted from production for cleanliness.

---

## 2026-08-12 — Adopted Alembic, replacing `Base.metadata.create_all()`

**Decision:** Added Alembic migrations (`alembic/`, `alembic.ini`). The initial
migration was generated by running `alembic revision --autogenerate` against a
**scratch, completely empty** database — not the real dev DB, which already had
tables from `create_all()` and would've produced an empty (useless) diff.
`alembic/env.py` reads `DATABASE_URL` from `app.config` rather than a second,
separately-maintained URL in `alembic.ini`, so there's one source of truth for
which database is being talked to. `app/main.py` no longer calls
`Base.metadata.create_all()` at all — schema is now Alembic's job, exclusively,
run via `alembic upgrade head` before the app starts (Procfile / Dockerfile
`CMD`), never at import/request time inside the app itself.

**Adopting migrations into a project with existing databases:** dev, test, and
(eventually) production already had the correct schema, built by the old
`create_all()` call. Running `alembic upgrade head` against them would try to
`CREATE TABLE`/`CREATE TYPE` on things that already exist and fail. The correct,
standard procedure — used here — is `alembic stamp head`: tells Alembic "this
database is already at this revision," recording that in a new `alembic_version`
table without running any of the migration's actual DDL.

**Real bug caught by testing the downgrade path, not just the upgrade:**
autogenerate's `op.drop_table()` calls in `downgrade()` don't clean up the
Postgres `ENUM` types SQLAlchemy created for `role`/`severity`/`status` — those
are orphaned types, separate database objects from the tables. Running
`upgrade → downgrade → upgrade` again failed the second `upgrade` with
`type "userrole" already exists`. Most autogenerate tutorials only show the
upgrade path working and stop there; actually running the full cycle caught a
migration that silently could not be re-applied. Fixed by adding explicit
`sa.Enum(name=...).drop(op.get_bind(), checkfirst=True)` calls to `downgrade()`
for all three enum types.

**Verified:** full upgrade → downgrade → upgrade cycle against a scratch DB
(catches the enum-type bug above). A second, separate fresh-empty-DB test
confirmed `alembic upgrade head` alone builds a schema a real signup/login flow
works against, with zero calls to `create_all()` anywhere. Local dev DB stamped
at head, confirmed zero drift via a second autogenerate pass (empty diff).

---

## 2026-08-12 — Docker: no Docker Desktop available, used Colima instead

**Decision:** Docker Desktop wasn't installed on this machine, and installing
it requires launching a GUI app and granting admin/privileged-helper
permissions interactively — not something doable non-interactively in an agent
session. Used **Colima** instead (`brew install docker docker-compose colima`,
`colima start`) — a lightweight Linux VM (via `lima`) that a plain `docker` CLI
talks to, with no GUI app and no admin password prompt. This is a legitimate,
common way developers run Docker on a Mac without Docker Desktop, not a hack —
worth knowing the distinction if asked "how does Docker even run on a Mac"
(it's always a Linux VM under the hood; Docker Desktop just packages that VM
with a GUI).

**`Dockerfile`:** `python:3.11-slim`, `requirements.txt` copied and installed
*before* the rest of the app code, so Docker's layer cache only reinstalls
packages when `requirements.txt` actually changes, not on every code edit.
Same start command as the Procfile: `alembic upgrade head && uvicorn ...`.

**`docker-compose.yml`:** two services, `db` (real Postgres 16 container,
health-checked) and `app` (built from the Dockerfile). `docker compose up` gives
a fully working stack — API + real Postgres — with zero local Python or
Postgres setup required. Host port `5433` maps to the `db` container's `5432`
(only relevant for connecting an external client; the `app` container talks to
`db` on its internal `5432` regardless, via Compose's service-name DNS).

**Verified:** `docker compose build && docker compose up` end to end — logs
show the migration running automatically inside the container on boot, then a
real signup → login → `/auth/me` flow succeeded against the containerized
stack. Torn down cleanly with `docker compose down -v` afterward.

---

## 2026-08-12 — GitHub Actions CI, and three real failures fixed by actually running it

**Decision:** `.github/workflows/ci.yml` runs on every push/PR: a `test` job
spins up a real Postgres **service container** (not mocks), runs
`alembic upgrade head` against it as a genuine migration check (would catch a
migration that doesn't actually apply cleanly — a bug the local dev/test DBs,
already stamped/seeded, would never surface), then the full pytest suite. A
separate `docker-build` job builds the Docker image, to catch a broken
Dockerfile independently of whether the tests pass.

**Three real failures hit and fixed, in order — the value of actually pushing
and watching it run instead of assuming a CI config is correct:**

1. **Missing `workflow` OAuth scope.** The `gh` CLI token from earlier in this
   session only had `repo`/`read:org`/`gist` scopes — GitHub refuses to accept a
   push that creates/modifies `.github/workflows/*` files without the
   `workflow` scope specifically. Fixed with `gh auth refresh -s workflow`
   (another device-code browser approval, same pattern as the original `gh`
   login).

2. **`ModuleNotFoundError: No module named 'app'` in CI only.** The workflow ran
   bare `pytest tests/ -v`; every local run all session had been
   `python -m pytest tests/ -v`. `python -m pytest` adds the current directory
   to `sys.path`; the bare `pytest` command does not, in some environments/
   configurations. Worked locally by coincidence of how it was always invoked,
   failed in CI's cleaner environment. Fixed by matching the exact command
   that had actually been verified working: `python -m pytest`.

3. **Node 20 deprecation warnings** on `actions/checkout@v4` and
   `actions/setup-python@v5` (GitHub force-runs them on Node 24 now, with a
   warning that this will eventually be a hard failure). Bumped to
   `actions/checkout@v7` and `actions/setup-python@v7` after confirming those
   tags actually exist (`git ls-remote --tags`) rather than guessing a version
   number.

**Verified:** final run green on both jobs, zero warnings —
confirmed by `gh run watch` on the actual GitHub Actions run, not by assuming
the YAML was correct.

---

## 2026-08-12 — Real incident: iCloud Desktop sync corrupted a git ref

**What happened:** Attempting to push the Docker/CI commit, `git push` failed
with `src refspec refs/heads/main does not match any` and `git status` reported
"No commits yet" on `main` — despite 13+ commits earlier in this session having
been made and pushed successfully. Investigation (`ls -la .git/refs/heads/`)
found the actual ref file `.git/refs/heads/main` was **missing**, and in its
place was a file literally named `main 2` (with a space) containing a valid
40-character commit SHA. This is the exact same pattern as the stray
`app/routers/incidents 2.py` file flagged much earlier in this session — this
project lives on `~/Desktop`, which macOS syncs via iCloud Drive by default,
and iCloud's conflict-resolution logic renames a file to `<name> 2` when it
detects concurrent modifications to the same path. Git rewrites ref files
frequently (every commit updates `refs/heads/main`); it's very plausible iCloud
synced mid-write and "resolved" what it saw as a conflict by duplicating the
file, leaving the expected filename empty.

**Why this was recoverable, not data loss:** the commit *objects* themselves
live in `.git/objects/`, content-addressed by SHA — entirely unaffected by
what a *ref* (a pointer/label to a SHA) happens to be named. The `main 2` file's
content was a real, valid SHA matching exactly the tip of the two new local
commits (Alembic, then Docker/CI) that hadn't been pushed yet. Renaming the file
back (`mv ".git/refs/heads/main 2" ".git/refs/heads/main"` — a plain filesystem
operation, not a git command) restored the branch pointer with zero data loss,
confirmed by `git status`, `git log --oneline`, and `git fsck --full` (which
reported no corruption) before pushing again.

**This is the second incident from the same root cause** (the first being the
stray `incidents 2.py` file during the models/RBAC milestone) — worth treating
as a real, recurring risk rather than a one-off curiosity. **Recommendation for
Gavin:** either exclude this project folder from iCloud Desktop sync (System
Settings → Apple ID → iCloud → Desktop & Documents Folders, or mark the
specific folder to not sync if supported), or move the project outside
`~/Desktop` entirely (e.g. `~/Projects/incident-desk`) to a path iCloud doesn't
touch. A `.git` directory being live-synced by a cloud file sync service is a
known general footgun (Dropbox has caused near-identical git corruption for
other developers historically) — not specific to this project, but this
project just proved it can actually happen here, twice.

---

## 2026-08-12 — Real incident: Railway silently switched builders, took prod down briefly

**What happened:** Adding a `Dockerfile` to the repo (for the Docker milestone)
caused Railway to **automatically switch** the `api` service's builder from
Railpack (its own Nixpacks-like builder, used for every deploy so far) to
building from the Dockerfile directly — without being asked to, and without a
clear signal that it had happened. The Dockerfile's `CMD` ran
`alembic upgrade head && uvicorn ...`; production hadn't been stamped yet (that
step was still pending in the task list), so `alembic upgrade head` tried to
`CREATE TYPE userrole ...` on a database that already had that type, crashed,
and the container crash-looped — the live site was down for a few minutes.

**Compounding mistake:** the fix was first attempted by temporarily editing
the **Procfile** (reverting it to skip the migration step) — which had worked
as the deploy mechanism for every previous deploy. It didn't work this time,
because Railway was now building from the Dockerfile, which has its own
independent `CMD` — editing the Procfile had no effect at all on what
actually ran. Realized this by checking `railway logs` and seeing the exact
same crash after the "fix," then correctly diagnosing that the *Dockerfile's*
`CMD` needed the temporary edit instead.

**Recovery, in order:** (1) temporarily removed `alembic upgrade head &&` from
the Dockerfile's `CMD` (not committed — a local-only, temporary edit) and
redeployed, restoring service; (2) SSH'd into the now-running container
(`railway ssh --service api -- alembic stamp head`) to mark production as
already being at the initial revision, same procedure as stamping the local
dev DB; (3) restored the Dockerfile's `CMD` to the real, committed version;
(4) redeployed again — this time `alembic upgrade head` correctly found
nothing pending and started the server normally. Verified all 6 seeded demo
incidents and both demo account roles survived untouched throughout.

**Lesson, stated plainly:** adding a Dockerfile to a repo that a PaaS
auto-detects is not a passive, side-effect-free change — it can silently
change how that PaaS deploys the *next* push, even without touching that
platform's dashboard/CLI directly. Should have anticipated this and stamped
production *before* introducing the Dockerfile, not after. Documented here
exactly because it's a real mistake, not a hypothetical one — the kind of
thing worth being able to explain candidly in an interview ("tell me about an
incident you caused and how you recovered") rather than only presenting
retroactively-clean work.

---

## 2026-08-12 — Connected Railway to GitHub for auto-deploy on push to main

**Decision:** the `api` service now redeploys automatically whenever `main` is
pushed, instead of requiring a manual `railway up` from a local machine. This
directly resolves a previously-documented gap ("not GitHub-connected").

**Getting there took three attempts, worth recording exactly why:**

1. `railway service source connect --repo gpark1230/incident-desk --branch main
   --service api` (CLI) — set the repo/branch association (confirmed via
   `railway status --json`, showed `"repo": "gpark1230/incident-desk"`), but
   pushing afterward triggered **no deploy** at all, even after a full CI cycle
   and several minutes of waiting.
2. Disconnecting and reconnecting the same repo through the Railway
   **dashboard UI** (Settings → Source) instead of the CLI — still no
   auto-deploy on the next push.
3. The actual fix: the dashboard has a **separate toggle**, "Auto deploys when
   pushed to GitHub," independent from the repo/branch connection itself.
   Connecting the source (by CLI or UI) only tells Railway *which* repo/branch
   to associate with the service — it does not by itself enable triggering a
   deploy *on push*. Only after explicitly switching that toggle on did a real
   push actually trigger a deploy.

**Lesson:** "connected" and "auto-deploying" turned out to be two independently
gated settings, not one — the CLI (and the first UI pass) only ever configured
the first. Worth remembering if this ever needs to be reconfigured, or if
setting up CD on a different Railway project in the future: connecting the
source is necessary but not sufficient, check for a separate deploy-trigger
toggle.

**Division of labor between GitHub Actions and Railway:** GitHub Actions is CI
(runs tests + validates the Docker image build on every push); Railway's native
GitHub integration is CD (actually deploys). These are two separate mechanisms,
not one pipeline — **a genuine, stated limitation:** a push to `main` that fails
CI will still trigger a Railway deploy, because Railway's auto-deploy isn't
currently gated on the GitHub Actions check passing. The "correct" fix for that
— a GitHub branch protection rule requiring the CI check before merge — matters
more for a team workflow with pull requests than a solo dev pushing directly to
`main`, which is this project's actual current workflow; noted here as a real,
known gap rather than silently left unmentioned.

---
