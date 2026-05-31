# Architecture Decision Log

A running log of design and technical decisions for tiny-lms. Each entry records
what was decided, why, and any implications worth remembering. Lightweight ADR style:
one document, newest decisions appended at the bottom.

**Status legend:** `Accepted` (decided and in effect) · `Proposed` (recommended, not yet
confirmed) · `Open` (raised, deliberately not decided yet).

---

## ADR-001: Project goal and stack

**Status:** Accepted

**Decision:** Build a Learning Management System with Python + FastAPI + PostgreSQL.
SQLAlchemy 2.x (async) as the ORM, managed as a uv workspace with a dedicated
`database` package.

**Rationale (user):** The system should be fast, maintainable, and extendable. The
project is also a learning vehicle — "I want to gain experience" — so we favor
understanding patterns over shipping speed.

**Implications:** Async stack throughout (`asyncpg` driver, async sessions). Teaching
mode is the default working style: the user implements, Claude guides and reviews.

---

## ADR-002: Co-teaching supported

**Status:** Accepted

**Decision:** A course can have multiple instructors.

**Rationale (user):** Chosen directly ("co-teaching").

**Implications:** Falls out of per-course roles (ADR-008) for free — `course_memberships`
is many-to-many, so multiple users with `role='instructor'` on one course = co-teaching.
No extra schema.

---

## ADR-003: Two distinct user↔course relationships

**Status:** Accepted

**Decision:** Separate "authority over a course" from "consumption of a course":
- `course_memberships` — who can teach/manage a course, and their role there.
- `enrollments` — who is taking the course as a student.

**Rationale:** Conflating teaching authority with student enrollment is the most common
LMS modeling mistake. They have different lifecycles (a membership grants edit rights;
an enrollment tracks progress, grades, completion).

---

## ADR-004: Materialized (per-user) enrollments

**Status:** Accepted

**Decision:** Enrolling a group creates one `enrollment` row **per user** (eager
expansion), tagged with the source group (e.g. `source = 'group:CS-101'`). Not a single
live group→course link.

**Rationale:** LMSes always end up needing per-user enrollment state (completion %,
certificate issued, dropped, withdrawal date, individual grades). A single live link
loses individuality and is painful to retrofit.

**Implications:** Adding a user to an already-enrolled group requires creating their
enrollment row (a job/handler), not just a membership change. Removing a user from a
group does not have to delete their enrollment/progress — we can preserve history.

**Open sub-question:** exact behavior when a user is removed then re-added to a group
(does old progress return?) — not yet decided.

---

## ADR-005: Assignment placement — course-level with optional topic

**Status:** Accepted

**Decision:** `assignments` always belong to a course (`course_id` required) and may
optionally belong to a topic (`topic_id` nullable).
- `topic_id` set → topic-level assignment (shows under that topic).
- `topic_id` NULL → course-level assignment (finals, projects, exams).

**Rationale:** Supports both contextual per-topic assignments and cross-cutting
course-wide assignments. Matches how Moodle/Canvas model it.

---

## ADR-006: Hybrid content storage

**Status:** Accepted

**Decision:** `content_items` support both self-hosted file blobs **and** external URLs,
in a single table distinguished by a `kind` field.

**Rationale (user):** "Should be able to store fileblobs yourself but also to store
external urls."

**Open sub-questions:**
- Single table with nullable columns vs. single table + JSONB payload vs. joined-table
  inheritance — not finalized. JSONB payload was flagged as most extensible (e.g. adding
  a "quiz" kind later with no migration).
- Blob backend: S3-compatible object storage (MinIO local / S3 prod) vs. local
  filesystem — not decided.

---

## ADR-007: Soft delete

**Status:** Accepted

**Decision:** Use soft delete (`deleted_at TIMESTAMPTZ NULL`) on entities that may have
dependent records (courses, topics, posts, assignments, etc.). `NULL` = live.

**Rationale (user):** "Soft delete should be enough for the start." Simplicity for the
initial version; preserves data tied to submissions/grades.

**Implications / open items:**
- Enforcement mechanism — **Decided.** A global `do_orm_execute` event listener applies
  `with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at == None, ...)` to every
  ORM query, so `deleted_at IS NULL` is filtered automatically (including relationship
  loads, via `propagate_to_loaders=True`). An `include_deleted=True` execution option is
  the escape hatch to bypass the filter. Lives in `models/mixins.py`.
- Cascade behavior (soft-deleting a topic → its posts/assignments) — **Open.**
- Interaction with unique constraints (does a deleted slug block reuse?) — **Open.**
- Note: the global filter applies to ORM `UPDATE`/`DELETE` executions too (not just
  `SELECT`), so bulk writes also skip soft-deleted rows by default — usually desired, worth
  remembering.

---

## ADR-008: Per-course roles

**Status:** Accepted

**Decision:** Roles are scoped per course, stored on `course_memberships`
(`user_id`, `course_id`, `role`). A user can be an instructor in one course and a student
in another.

**Rationale (user):** "Roles should be per course."

---

## ADR-009: Table naming convention — lowercase plural

**Status:** Accepted

**Decision:** Table names are lowercase and plural (`users`, `courses`,
`course_memberships`, `content_items`). Python classes stay singular CapWords (`User`,
`CourseMembership`). File name = singular entity (`user.py`).

**Rationale:** Postgres folds unquoted identifiers to lowercase; capitalized names force
quoting everywhere. Lowercase plural is the SQLAlchemy/Django/Rails convention.
Consistency matters more than the specific choice.

---

## ADR-010: Primary key strategy — BIGINT identity

**Status:** Accepted

**Decision:** All primary keys are `BIGINT`. Use `mapped_column(BigInteger, ...)`
explicitly (SQLAlchemy's bare `Mapped[int]` maps to 32-bit `INTEGER`, which we do not
want).

**Rationale (user choice):** Simple, fast, small, easy to reason about in `psql`.
Acceptable that row counts/ordering are visible in URLs for this project.

**Open sub-question:** `Identity(always=False)` (allows explicit ID inserts in
seeds/tests — `GENERATED BY DEFAULT AS IDENTITY`) vs. `always=True` (DB-managed only).
Not yet decided. Current `User.id` uses `primary_key=True` without `Identity()`, so it
still relies on the legacy sequence mechanism rather than modern identity columns.

---

## ADR-011: Progress tracking — all activities, implicit + explicit completion

**Status:** Accepted (granularity) · **Open** (storage model)

**Decision (user):** Track progress across all activities. Completion has two mechanisms:
- **Implicit / auto-complete** — e.g. a video auto-completes when played to the end.
- **Explicit** — e.g. a post is completed when the user clicks "mark as completed."

**Rationale (user):** Direct description of desired UX.

**Open sub-questions (explicitly not decided):**
- Storage model: state-only vs. event-log vs. both (events + projected state).
- Polymorphic trackable (`trackable_type` + `trackable_id`) vs. separate per-activity
  progress tables vs. supertype `activity` table.
- Whether post completion is derived from its content items or tracked independently.
- Video completion rule details (furthest-position vs. cumulative-watch, anti-skip,
  heartbeat frequency, resume).
- What happens to completion when new posts are added to an already-completed topic, or
  when a post is soft-deleted.

---

## ADR-012: Configuration via pydantic-settings

**Status:** Accepted

**Decision:** Settings live in `database/config.py` as a `Settings(BaseSettings)` with
`env_prefix="DB_"`, reading from `.env`, tolerating unrelated vars (`extra="ignore"`).
The async DB URL is composed in a `DATABASE_URL` property
(`postgresql+asyncpg://...`). Exposed two ways:
- `get_settings()` (cached via `lru_cache`) — for FastAPI `Depends`, overridable in tests.
- `settings = get_settings()` module-level export — for Alembic env, scripts, and
  `connection.py`.

**Rationale (user choice):** Wanted both access styles. `lru_cache` makes them return the
same instance.

**Convention:** FastAPI code uses `Depends(get_settings)`; everything else imports
`settings`.

---

## ADR-013: Database driver — asyncpg

**Status:** Accepted

**Decision:** Use `asyncpg` as the async Postgres driver. Connection URLs carry the
`postgresql+asyncpg://` tag so SQLAlchemy selects the async driver (omitting it silently
falls back to the sync driver and breaks async calls).

---

## ADR-014: Alembic location — workspace root

**Status:** Accepted

**Decision:** Alembic lives at the workspace root (`alembic/`, `alembic.ini`), not inside
`packages/database/`. `env.py` imports `Base` from `database.connection` and the models
via `from database.models import *` so they register on `Base.metadata`. The DB URL is
injected in `env.py` via `config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)`;
the `sqlalchemy.url` placeholder in `alembic.ini` is dead.

**Rationale:** One database = one Alembic environment. Future packages (FastAPI app,
worker, CLI) are consumers of the `database` package, not co-owners of schema. Migrations
are an operational/deployment artifact, so they sit at the root, run with a consistent
cwd. (`asyncpg` stays a dependency of the `database` package, since that package opens
connections.)

**Setup notes:** Use the async template (`alembic init -t async`). Treat
`--autogenerate` output as a draft to review, never as final.

---

## ADR-015: Constraint naming convention

**Status:** Accepted

**Decision:** Attach a `naming_convention` to `Base.metadata` so all constraints and
indexes get deterministic names:

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

**Rationale:** Set before the first migration so names are stable forever. Without it,
auto-named constraints can't be reliably referenced by later `DROP`/`ALTER` migrations.

**Caveat:** `CHECK` constraints must be given an explicit `name=` (the `ck` template uses
`%(constraint_name)s`, which is author-supplied, not derived).

---

## ADR-016: Timestamp columns — timezone-aware (TIMESTAMPTZ)

**Status:** Accepted

**Decision:** All instant-in-time columns use `DateTime(timezone=True)`
(Postgres `TIMESTAMPTZ`). `created_at`/`updated_at` are DB-generated via
`server_default=func.now()` (and `onupdate=func.now()` for `updated_at`), provided by a
shared `TimestampMixin`.

**Rationale:** `TIMESTAMPTZ` stores an unambiguous UTC instant (it does not store a zone),
making timestamps independent of where code runs (dev laptop, CI, prod, containers) and
immune to DST ambiguity. Same storage size and performance as naive `TIMESTAMP`. Using
`func.now()` keeps generation DB-side, sidestepping naive-datetime bugs in Python.

**Rule:** On the Python side, only ever use timezone-aware datetimes
(`datetime.now(UTC)`), never `datetime.utcnow()` or naive `datetime.now()`.

---

## ADR-017: String length constraints

**Status:** Proposed (pattern agreed; per-column lengths being applied)

**Decision:** Constrain string columns with `String(n)` (Postgres `VARCHAR(n)`) where a
sensible max exists; use `Text` for genuinely long-form fields. Reuse common lengths via
`Annotated` type aliases (e.g. `str100`, `str255`) kept in a shared module. Length is also
validated at the Pydantic/API layer (`Field(max_length=...)`) for clean 422s — the DB
constraint is the guarantee, the Pydantic one is UX.

**Rationale:** In Postgres `VARCHAR(n)` and `TEXT` perform identically; the limit is
purely input validation. Apply it where rejecting over-long input is desired
(email ≈ 255, names ≈ 100).

**Open item:** `password_hash` length is deliberately **not** guessed — it depends on the
hashing algorithm (bcrypt 60, argon2 ~95+ and variable). Until the hasher is chosen, keep
it `Text` (unbounded) or size with generous headroom. Choosing too small silently
truncates hashes and locks users out. **Hasher choice: Open.**

---

## ADR-018: Data-access layer — pure-persistence repositories in the `database` package

**Status:** Accepted

**Decision:** Reusable per-entity persistence functions (create/read/update/soft-delete)
live in the **`database`** package (e.g. `database/repositories/user.py`), not in `api`.
They are **pure persistence**: plain async functions that take an `AsyncSession`, operate
on ORM objects, and contain no business logic.

**Rationale:** `database` is the package every consumer depends on (`api`, plus future
worker/CLI/seed scripts). Putting CRUD in `api` would force non-HTTP consumers to depend on
FastAPI just to touch data. Pattern chosen is a **module of async functions** (FastAPI-docs
style), not a repository class — simplest thing that works (per project rules); revisit only
if swap-ability/mocking is actually needed.

**Contract:**
- Functions take `session: AsyncSession` as the first arg; they `flush()` (to get generated
  ids) but **never `commit()`** — the **caller owns the transaction boundary** (an `api`
  `Depends(get_session)` that commits on success / rolls back on error; or an
  `async with async_session()` block in a script). This keeps multi-step operations atomic.
- Functions take already-derived values (`password_hash`, not raw `password`).
- They return ORM objects or `None`, never HTTP shapes; they raise domain/DB errors, never
  `HTTPException`.
- **No business logic**: no password hashing, no email-format validation, no
  duplicate-email pre-checks. Uniqueness is enforced by the DB constraint
  (`uq_users_email`) — `create_user` attempts the insert and lets `IntegrityError`
  propagate; `api` translates it (e.g. 409). This also avoids the check-then-insert race.
- Soft delete uses the model's `soft_delete()` (sets `deleted_at`), not a SQL `DELETE`. The
  global filter (ADR-007) hides soft-deleted rows from normal reads automatically;
  `include_deleted=True` is the escape hatch for restore flows.

**Boundary:** business rules (hashing, validation, authorization) live one layer up, in
`api`'s service/endpoint layer. `database` stays pure persistence.

**Input DTOs:** write operations take a Pydantic **persistence DTO** that lives in the
`database` package (`database/schemas/`), e.g. `UserCreate(first_name, last_name, email,
password_hash)`. This DTO carries already-derived values (`password_hash`, plain `str`
email — **not** `EmailStr`); format validation and hashing happen in `api`'s *request*
model, which is a separate schema. Keeping the persistence DTO in `database` avoids
inverting the dependency (api → database, never the reverse) and keeps `email-validator`
out of the `database` package. Implementation pattern:
`User(**data.model_dump())` → `session.add` → `await session.flush()` (no commit).

---

## Cross-cutting mixins (current state — as implemented)

`packages/database/src/database/models/mixins.py` contains both mixins, in 2.0
`Mapped[...] = mapped_column(...)` style:

- **`TimestampMixin`** — `created_at`, `updated_at`, both `DateTime(timezone=True)`,
  `nullable=False`, `server_default=func.now()` (DB-side, matches ADR-016). `updated_at`
  also has `onupdate=func.now()` (SQLAlchemy-side; a raw SQL `UPDATE` won't bump it — a
  trigger would be needed for that, deemed unnecessary for now).
- **`SoftDeleteMixin`** — `deleted_at` (`DateTime(timezone=True)`, `nullable=True`,
  default `None`), plus `soft_delete()` (sets `deleted_at = func.now()`) and `restore()`
  (sets it back to `None`). Backed by the global query filter described in ADR-007.

Intended inheritance order: `class User(TimestampMixin, SoftDeleteMixin, Base)`.

**Fixes applied (previously flagged divergences, now resolved):**

1. ✅ `SoftDeleteMixin` now exists (ADR-007).
2. ✅ Timestamps use `server_default=func.now()` (DB-side), not client-side `default=`
   (matches ADR-016).
3. ✅ Mixins use 2.0 `Mapped`/`mapped_column` style (consistent with `user.py`).
4. ✅ `created_at` annotation corrected to `Mapped[datetime]` (was wrongly `| None` against
   `nullable=False`); `deleted_at` annotation corrected to `Mapped[datetime | None]`
   (was wrongly non-optional against `nullable=True`), which let the `# pyright: ignore`
   in `restore()` be removed.
5. ✅ `soft_delete()` uses `func.now()` (DB clock) instead of naive `datetime.now()`
   (matches the ADR-016 no-naive-datetime rule).

**Still verify against the already-generated migration:** the first migration
(`317266991ac2_create_user_table.py`) was autogenerated *before* some of these changes.
Confirm it reflects the current mixin state (server defaults, `deleted_at` column) — if
not, regenerate or hand-edit before running `upgrade`.

---

## Open decisions backlog

Consolidated list of things explicitly raised but not yet decided:

1. Enrollment behavior on group remove/re-add (ADR-004).
2. ContentItem storage shape + blob backend (ADR-006).
3. Soft-delete cascade behavior and unique-constraint interaction (ADR-007). *(Enforcement
   mechanism — resolved: global `with_loader_criteria` filter.)*
4. `Identity(always=False)` vs `always=True` (ADR-010).
5. Progress storage model, polymorphism, completion bubbling, edge cases (ADR-011).
6. `password_hash` hashing algorithm and column size (ADR-017).
7. ~~Repository pattern vs. direct `Depends(get_session)` in FastAPI.~~ **Resolved (ADR-018):**
   pure-persistence async functions in the `database` package; caller owns the transaction.
