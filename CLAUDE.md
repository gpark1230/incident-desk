# Project: IncidentDesk — Security Incident Tracking API

## What this is

A backend REST API for tracking and managing security/IT incidents — similar in spirit to internal tools Gavin already manages professionally (CrowdStrike alerts, ticketing, incident documentation) as an IT Operations and Security Associate at KLCP LLP, but built here from the engineering side as a portfolio piece for backend engineering job applications.

Chosen deliberately over a generic CRUD/todo app because it has real relational complexity, real authorization logic (not just authentication), and a defensible interview narrative tied directly to Gavin's actual professional background. The goal is to stand out in a pool of junior backend applicants who mostly ship generic tutorial clones.

## Tech stack

- FastAPI
- PostgreSQL
- SQLAlchemy ORM
- OAuth2 / JWT auth (e.g. `python-jose` or `pyjwt`, `passlib`/`bcrypt` for password hashing)
- pytest
- Deployment: start with a simple PaaS (Render, Railway, or Fly.io) for the first working deploy. Docker + CI/CD (GitHub Actions) get layered on afterward as a separate phase — not required for the first deploy. Deeper AWS usage comes later in the broader roadmap, not blocking for this project.

## Core features

- **Users**: signup/login, JWT auth, roles (`admin` / `analyst` / `viewer`)
- **Incidents**: CRUD — create, read, update status, close. Fields: severity, status, assigned_to, created_by, timestamps
- **Comments**: one-to-many notes attached to an incident — real relational complexity beyond a single flat table
- **Audit log**: append-only log recording every state change on an incident (who did what, when). Never editable or deletable — mirrors real SOC/compliance tooling patterns. This is the differentiator feature.
- **RBAC enforcement**: viewers = read-only, analysts = create/update incidents + comments, admins = full control + user management
- **Filtering/pagination** on the incident list (status, severity, assigned analyst, date range)
- **pytest suite** covering: auth flow, RBAC enforcement (e.g. a viewer hitting a POST route should get a 403), and core incident CRUD flows

## Recruiter visibility — this is a real requirement, not an afterthought

This project needs to actually get seen and understood by recruiters/hiring managers glancing at a GitHub profile for a few seconds, not just function correctly. Build these in as real deliverables:

- A genuinely good `README.md`: what the project is and why it exists (the security/incident-tracking angle, tied to Gavin's real professional background), the tech stack, a short feature list, setup/run instructions, and a live demo link once deployed. A screenshot or short GIF of the `/docs` page or a sample request/response is worth including.
- The GitHub repo needs to be public, with clean, real incremental commit history (not one giant commit) — commit messages should read like a real engineer's, not "final final v2."
- A live, clickable deployed link (or at minimum a publicly reachable `/docs` page) that actually works when clicked, not just "works on my machine."

Don't leave this until the very end — a README with real content should exist from early in the build and get updated as features land, same as the commit history.

## Build philosophy — read this before writing any code

Gavin is a self-taught backend learner working toward a backend engineering job, currently employed at KLCP LLP but with limited remaining runway there. His learning history so far: Python fundamentals, git/GitHub, command line, HTTP fundamentals, decorators, venvs, FastAPI basics + full CRUD routes, SQL fundamentals, PostgreSQL + SQLAlchemy ORM (models, sessions, queries), and OAuth2/JWT concepts (understood conceptually — auth vs. authorization, password hashing, JWT structure — but not yet implemented in real code).

He explicitly chose to have this project built collaboratively/primarily by Claude rather than writing every line himself, given the real time constraint. This tradeoff was discussed openly beforehand: it's faster, but risks weak performance in live coding/pairing interview rounds or on-the-job debugging if understanding stays shallow. Mitigation, please follow it:

1. As you build each piece, explain what it does and why in plain, simple language as you go — don't just drop finished code silently.
2. Do NOT pause after each milestone to make Gavin explain it back — he wants to build first and understand the whole project in one pass once it's finished, not be gated milestone-by-milestone (his explicit correction, 2026-08-12, after the original per-milestone check-in plan proved unwanted in practice). Keep explaining as you go per (1), just don't block progress on him repeating it back.
3. Favor common, standard, explainable patterns over clever or obscure ones — this needs to hold up under interview questioning, not just work.
4. Keep explanations plain-language first (short sentences, concrete examples, minimal unexplained jargon) — this is what has actually worked for Gavin so far, confirmed repeatedly.

## Status

As of Aug 12, 2026, all core features from this file are built, tested, and deployed live:

- Auth (JWT signup/login/`/auth/me`), RBAC (`viewer`/`analyst`/`admin`), append-only audit log, comments, filtering/pagination on the incident list — all done, all with real curl/pytest verification, not just "looks right."
- 19 pytest tests (auth, RBAC enforcement, incident/audit-log behavior) run against a real second Postgres DB, not mocks. All passing.
- Public GitHub repo with real incremental commit history: https://github.com/gpark1230/incident-desk
- README with rationale, setup instructions, sample request/response, and API table.
- Live deploy on Railway: https://api-production-1570.up.railway.app/docs
- Full build reasoning — every non-trivial decision, alternative considered, and bug hit along the way (including a real passlib/bcrypt incompatibility) — is in [`DECISIONS.md`](./DECISIONS.md), not just this file.

**Known gaps, honestly stated (good "what would you do next" interview answers):**

- No Alembic migrations — `app/main.py` calls `Base.metadata.create_all()` on startup as a stand-in. Fine with no real data yet; not a substitute for real migrations once there is.
- No admin-promotion endpoint — the only way to create an `analyst`/`admin` account is direct DB access (`psql` or, in tests, a fixture that bypasses the API). Signup can only ever create a `viewer`, by design, but there's no in-API path to promote someone either.
- Railway `api` service deploys via `railway up` from the local CLI, not GitHub-connected auto-deploy on push — pushing to `main` does not currently redeploy the live instance.
- No Docker/CI-CD yet (planned as a later phase per the Tech stack section above, not blocking).
- No screenshot/GIF of `/docs` in the README yet — a sample request/response was used instead since no browser/screenshot tooling was available in the build session.

Update this file as the project progresses — milestones hit, real decisions made, bugs solved worth remembering for the interview narrative. Treat this file as the persistent memory of the project across every future Claude Code session here.
