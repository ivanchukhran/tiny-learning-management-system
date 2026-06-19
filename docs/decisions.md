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

**Status:** ~~Accepted~~ · **Superseded by ADR-021** — unified into a single
`course_memberships` link so one permission system covers all participants.

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

**Status:** Accepted (per-course scoping) · **storage superseded by ADR-021/ADR-022** —
`role` moves from an inline column to a `role_id` FK into a `roles` table.

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

**Query/mutation shape (as implemented for `user`):**
- **Predicate over kwargs.** Read/update/delete functions accept
  `*criteria: ColumnExpressionArgument[bool]` and splat them into `.where()`. Callers pass
  real column expressions (`User.id == x`, `User.email == "..."`, `User.last_name == "..."`).
  Chosen over `**kwargs` equality filters because predicates give the full expression
  language (comparisons, `IN`, `OR`, `LIKE`) for free. Acceptable leak of `User.*` into
  callers because callers are in-package/`api`, not an external boundary.
- **Single vs. bulk split** (decided per-operation):
  - `get_user` → `scalar_one_or_none()` (`User | None`; raises `MultipleResultsFound` if the
    predicate is non-unique — pins the "caller asserts uniqueness" contract). `list_users` →
    `Sequence[User]` (empty → `[]`, never `None`).
  - `update_user` is **load-then-mutate**: `get_user` → `setattr` the
    `model_dump(exclude_unset=True)` fields → `flush` → return the fresh object (or `None`
    if no match). `update_users` is **bulk** `update().values()` → returns `rowcount`.
  - `delete_user` / `restore_user` are predicate-bulk → return `rowcount`.
- **`update_user` must `refresh(["updated_at"])` after flush.** `updated_at`'s `onupdate`
  value is computed server-side, so the attribute is *expired* post-flush; reading it without
  a refresh triggers a lazy `SELECT` = async IO outside `await` → `MissingGreenlet`. (INSERT
  needs no such refresh — server defaults return via `RETURNING`; UPDATE `onupdate` does not.)
- **`restore` requires `include_deleted=True`.** A plain bulk update setting `deleted_at=None`
  would get `AND deleted_at IS NULL` appended by the global filter and match **zero** deleted
  rows. `restore_user` sets `.execution_options(include_deleted=True)` to bypass it. This is
  why restore can't be a one-liner symmetric with delete.
- **Empty bulk update is a timestamp-only no-op, not an error.** An all-unset `UserUpdateDb`
  dumps to `{}`, but the `update(User)` *construct* still emits `SET updated_at=now()`
  because it honors the column's `onupdate` (unlike a hand-written raw SQL string — see the
  mixins note). So `update_users(..., UserUpdateDb(), ...)` matches rows, bumps the timestamp,
  changes no caller field, and returns the match count. No empty-`SET` error → no guard needed.

**Update DTO:** partial updates take `UserUpdateDb` — same fields as `UserCreateDb` but all
`Optional` with `None` defaults. `model_dump(exclude_unset=True)` yields only the fields the
caller explicitly set, so untouched columns are preserved (not nulled). Trade-off: can't
distinguish "set to NULL" from "leave alone", which is fine because no `User` column is
nullable; revisit if a nullable, clearable column is added.

**Boundary:** business rules (hashing, validation, authorization) live one layer up, in
`api`'s service/endpoint layer. `database` stays pure persistence.

**Input DTOs:** write operations take a Pydantic **persistence DTO** that lives in the
`database` package (`database/schemas/`), e.g. `UserCreateDb(first_name, last_name, email,
password_hash)`. This DTO carries already-derived values (`password_hash`, plain `str`
email — **not** `EmailStr`); format validation and hashing happen in `api`'s *request*
model (a separate schema, e.g. `UserCreate`). The `Db` suffix distinguishes the persistence
DTO from the API contract model and avoids the name collision between the two layers. Keeping the persistence DTO in `database` avoids
inverting the dependency (api → database, never the reverse) and keeps `email-validator`
out of the `database` package. Implementation pattern:
`User(**data.model_dump())` → `session.add` → `await session.flush()` (no commit).

---

## ADR-019: Authentication — server-side sessions in an httpOnly cookie

**Status:** Accepted (design) · implementation pending

**Decision:** Authentication is **session-based** (server-side state), not token/JWT.
The session credential travels in an **`httpOnly`, `Secure`, `SameSite=Lax` cookie**,
with the SPA and API served behind a **single origin via a reverse proxy**.

**Rationale (why sessions over JWT for *this* project):**
- **Frontend undecided (SPA vs htmx).** A cookie works for both; a bearer-header scheme
  silently commits to the SPA. Cookie transport keeps the frontend question open.
- **Instant revocation matters.** Accounts are admin-managed and users are soft-deleted;
  "disable a user → their logins stop now" is a one-row delete with sessions. JWT would
  need a server-side blocklist — i.e. server state rebuilt badly.
- **Per-course authz is mutable and granular (ADR-008).** Almost every request hits the DB
  to authorize anyway, so the JWT "no server lookup" benefit evaporates.
- **No JWT-shaped problem.** No third-party API consumers, no fleet of services, no
  cookie-less mobile client — the scenarios where JWT pays off are all absent.
- **The hybrid tell.** Reaching for refresh tokens reintroduces a server store; skip the
  detour and store sessions directly.

**Same-origin-via-proxy consequence:** `SameSite=Lax` is sufficient CSRF defense **because
mutations use POST/PATCH/DELETE** (Lax still sends the cookie on top-level GET navigations,
so no state-changing GETs). No separate CSRF token needed; no CORS / `credentials` dance.
True cross-origin would have forced `SameSite=None` + CORS-credentials + CSRF tokens — the
proxy avoids all three.

**Session model (`sessions` table):**
- `id` (BIGINT identity, per ADR-010), `user_id` (FK → users), `hash`, plus the two
  expiry **event** timestamps below.
- **`hash` stores a digest of the token, not the token.** The raw token is a CSPRNG value
  (≥256 bits) that lives only in the cookie. We store a **deterministic, fast** hash
  (SHA-256, unsalted) — *opposite* of `password_hash`'s argon2. Reasoning: the token is
  the lookup key (no "username" to find the row by), so the hash must be deterministic to
  support `WHERE hash = ?`; and a 256-bit random token is unguessable, so a slow/salted
  hash defends against nothing here. Hashing-at-rest means a DB leak doesn't hand out live
  sessions. `hash` is unique + indexed (the per-request lookup key).
- **No `SoftDeleteMixin`.** Logout and expiry are **hard deletes**; the global soft-delete
  filter must not touch this table.

**Expiry — hybrid (idle timeout under an absolute ceiling), stored as events:**
- Two facts stored as **events**, not deadlines: `created_at` (absolute ceiling anchor) and
  `last_seen_at` (idle anchor). Windows are app constants (`IDLE_WINDOW`, `MAX_LIFETIME`).
  Events chosen over stored deadlines so the windows can be **retuned globally** later
  (mirrors the events-vs-state reasoning in ADR-011). Trade-off accepted: validity uses
  interval math instead of plain column comparisons.
- A session is valid iff **both** `now() < last_seen_at + IDLE_WINDOW` **and**
  `now() < created_at + MAX_LIFETIME`. Keeping them as two **independent** conditions means
  the idle bump never needs clamping to the ceiling — the `AND` does it for free.
- **Why hybrid:** idle timeout bounds the *abandoned shared-computer* session; the absolute
  ceiling bounds the *stolen-but-kept-alive* session (pure sliding would let a hijacked,
  pinged token live forever). Each defends a threat the other leaves open.
- **Lazy bump:** `last_seen_at` is pushed forward only when it is more than a threshold
  stale, not on every request, to avoid turning a read-heavy LMS's every authed GET into a
  write. The ceiling (`created_at`) is never touched.

**Validation path (`get_current_user`, an `api` dependency):**
- read cookie → **hash it in the `api` layer** → repo looks the row up by `hash`, **joined
  to `User`** so the soft-delete filter rejects deleted users' sessions automatically →
  apply the two validity conditions → return the user or **401**.
- Repos stay pure persistence (ADR-018): they receive the **hash**, never the raw token,
  and never hash anything themselves.

**401 vs 403:** `get_current_user` failures (no cookie, bad hash, expired, deleted user) are
**401** (unauthenticated). Per-course permission failures are **403** (authenticated but
forbidden) and live in a *separate* authz dependency — not in `get_current_user`.

**Lifecycle (`api` layer):**
- **login:** `verify_password` (ADR-017) → mint token → insert session → `Set-Cookie`.
- **logout:** delete the one session row + clear cookie.
- **log out everywhere / password change:** delete *all* the user's session rows — the
  same primitive. ADR note: `update_password_endpoint` should drop the user's other
  sessions (currently it does not — **Open**, to wire when sessions land).

**DB is authoritative for expiry.** The cookie's `Max-Age` is only a browser hint; the
server enforces validity from the row. A cookie claiming validity past the DB's expiry loses.

**Open sub-questions (deliberately deferred):**
- Long quiet activity (e.g. reading an exam question for 35 min) trips the idle timeout —
  needs a **heartbeat** from the client or a window sized around exam behavior (which
  weakens the abandoned-computer defense). Tension unresolved.
- **Exam integrity must not depend on session liveness.** In-progress attempt state must
  live server-side and be resumable after re-login; sessions dying (crash, ceiling, admin)
  must not lose work. This is an *exam-attempt* modeling concern, not a session concern.
- `IDLE_WINDOW` / `MAX_LIFETIME` concrete values — **Open.**
- Where session constants live (`api/constants.py` vs a new auth module) — **Open.**
- Login brute-force throttle/lockout — **Open** (argon2 slows offline cracking, nothing
  yet rate-limits online guessing).
- Reaping expired rows (a row is prunable once *either* deadline passes) — **Open.**

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

## ADR-020: Authorization — two-level (global admin + per-course roles)

**Status:** Accepted (design) · implementation pending

**Decision:** Two independent authority levels:
- **Global:** `users.is_admin` (boolean) — absolute platform access; short-circuits every
  authorization check.
- **Per-course:** a role on the user's course membership (ADR-021) drives a permission set
  (ADR-022).

The two are orthogonal. Admin is **not** "the top course role" — it bypasses the per-course
system entirely, and admins hold no `course_memberships` rows.

**Rationale (user):** Admin is platform-wide and binary; per-course authority is scoped and
granular. Folding them into one enum/role would force every per-course check to special-case
the global case and leak admin into the membership table. A boolean + a short-circuit keeps
them cleanly separate.

**Implications:** `may()` (ADR-024) tests `is_admin` first and returns early. Admins need no
membership to act on any course.

**Open:** if a second global role ever appears (read-only support, billing), `is_admin: bool`
graduates to a `platform_role` field — deferred until a concrete second role exists (YAGNI).

---

## ADR-021: Unified course-membership link (supersedes ADR-003, storage of ADR-008)

**Status:** Accepted (design) · implementation pending

**Decision:** A single link table `course_memberships(id, user_id, course_id, role_id)`
represents **every** user↔course relationship. `role_id` is an FK to `roles` (ADR-022), not
an inline enum column.
- Replaces ADR-003's split (`course_memberships` for authority + `enrollments` for students)
  with one table whose `role` distinguishes `student` / `instructor` / future roles.
- Replaces ADR-008's role-as-column with role-as-FK.
- `unique(user_id, course_id)` — one role per user per course.

**Rationale (user):** Unify so a single permission system (defaults + per-user overrides,
ADR-022) covers *all* participants. "A student who may post news" becomes a per-user override
on their membership — impossible if students lived in a separate, override-less table. The
simplicity of one authorization path outweighed ADR-003's authority/consumption separation.

**Implications:**
- Co-teaching (ADR-002) still falls out for free: multiple memberships with `role=instructor`.
- The design-chat term "member" is recorded as the **`student`** role, matching existing
  vocabulary (ADR-003/004).
- **Progress/enrollment state** (ADR-004, ADR-011) was framed as living on `enrollments`.
  With that table gone, per-user progress/completion/grades must attach elsewhere — columns
  or a related table keyed off `course_memberships.id`, or a dedicated `enrollment_state`
  table. ADR-004's *materialization* intent still holds; only its host table changes.
  **Open sub-question** — not resolved here.

---

## ADR-022: Per-course permissions as data — role defaults + per-user grant/deny overrides

**Status:** Accepted (design) · implementation pending

**Decision:** RBAC stored as data ("Option C"), resolved on read:
- `roles(id, name)` — controlled vocabulary (ADR-023).
- `permissions(id, code)` — catalog of actions (`read_content`, `write_content`,
  `delete_content`, `enroll_members`, `assign_instructors`, …).
- `role_permissions(id, role_id, permission_id)` — per-role **defaults**;
  `unique(role_id, permission_id)`.
- `course_membership_permissions(id, course_membership_id, permission_id, grant: bool)` —
  per-user **overrides** on a membership; `grant=true` adds, `grant=false` revokes;
  `unique(course_membership_id, permission_id)`.

**Effective permissions** = role defaults, then overrides layered on top.

**Precedence:** an override always wins over the role default for that permission — an explicit
`grant=false` revokes a default-granted action (deny-wins relative to the default).

**Rejected alternatives:**
- **A — boolean column per action on the membership.** Every new action = a schema migration
  (column-per-verb tax); defaults copied per row → drift when a role's meaning changes.
- **B — nullable boolean columns (tri-state).** Solves drift but keeps the column-per-action
  migration tax once the action set grows (it will).

C keeps defaults **live** (change a `role_permissions` row → all memberships of that role
follow, no drift) and adds actions as **rows, not columns**.

**Consequences:**
- Every `may()` call does a small merge (defaults ∪/∖ overrides), not a single column read —
  accepted cost (see ADR-024 performance note).
- `unique(course_membership_id, permission_id)` prevents a contradictory grant+deny pair for
  the same cell.

---

## ADR-023: Permission-data ownership — defaults seeded (code-owned), overrides runtime

**Status:** Accepted (design) · implementation pending

**Decision:**
- `roles`, `permissions`, and `role_permissions` (the **defaults**) are **code-owned**:
  seeded and changed only via Alembic migrations. Changing a role's default capability is a
  deploy.
- `course_membership_permissions` (the **overrides**) are **runtime-owned**: created/edited
  by admins through the panel.

Two owners, two tables → no two-sources-of-truth, no drift.

**Seeding rule (avoids the hardcoded-id trap):** seed `roles` and `permissions` first; seed
`role_permissions` by **looking up each side by its natural key** (`roles.name`,
`permissions.code`) to get the real id — never a hardcoded surrogate id (ids are
insertion-order artifacts that differ across environments and test DBs).

**Required constraints:** `unique(roles.name)` and `unique(permissions.code)` — they make the
natural-key lookup sound *and* block duplicate vocabulary rows at runtime.

**Rationale:** roles/permissions are a fixed vocabulary the code references by name (in
`may()` and guards), changing rarely → migration-owned is correct and reproducible. Only
per-user exceptions must change without a deploy → those are the overrides.

**Implications:**
- Tests (testcontainers) need the seed rows present — run the seed in a migration so a
  fresh/test DB comes up with the vocabulary.
- A new permission ships as: new guarded endpoint (code) **+** a migration adding the
  `permissions` row and any `role_permissions` defaults — together.

---

## ADR-024: Authorization enforcement — `may()` + FastAPI dependency factory

**Status:** Accepted (design) · implementation pending

**Decision:** one resolver and one reusable route guard.

`may(db, user, action, course_id) -> bool`:
1. `if user.is_admin: return True` (ADR-020 short-circuit).
2. load the `course_membership` for `(user, course_id)`; `None` → `False`.
3. start from role defaults (`role_permissions` for that membership's role).
4. apply overrides (`course_membership_permissions`): `grant=true` adds, `grant=false`
   removes.
5. `return action in effective_set`.

**Route guard — dependency factory:** `require_permission(action: str)` returns an inner
dependency taking `course_id` (from the path), `current_user` (`Depends(get_current_user)`,
ADR-019), and `db`, raising **403** unless `may(...)`. The outer call bakes the action into a
closure; the inner reads the course at request time. `require_admin` is the slice-1 special
case: `Depends(get_current_user)` + raise 403 unless `is_admin`.

**Status codes (aligns with ADR-019):**
- unauthenticated (no/expired session) → **401**, already raised by `get_current_user`.
- authenticated but not permitted → **403**, raised by the guard.

**Open — 403 vs 404 existence-hiding:** for resources whose mere existence is sensitive, the
guard may return **404** instead of 403 to avoid confirming existence. Per-resource decision;
default 403; the factory takes an optional flag. Not decided per-endpoint yet.

**Performance note:** `may()` hits the DB per call; listing N courses = N resolutions. When it
bites, resolve once per request and cache on the request object — deferred, not a launch
concern.

---

## ADR-025: Admin bootstrap — `is_admin` column + CLI seed

**Status:** Accepted (mechanism) · implementation pending

**Decision:**
- `users.is_admin: bool`, `NOT NULL`, default `false` — the single global flag (ADR-020).
- **Never** expose `is_admin` in `UserCreate`/`UserUpdate` (`api/schemas/user.py`) or any
  request model — this closes the privilege-escalation hole (no self-promotion via the
  create/update body). *(Verified 2026-06: neither schema carries it today.)*
- The **first admin** is minted out-of-band by a **CLI command** (`create-admin <email>`)
  that looks up (or creates) the user and sets `is_admin=true`. Re-runnable; the only
  privileged path to admin.

**Rationale:** registration must not set the flag; admin grants admin; the CLI breaks the
chicken-and-egg and doubles as recovery / second-admin. Chosen over a hardcoded seed migration
because (a) migrations describe schema, not specific people; (b) the CLI is re-runnable and
has full app context (can hash a password). A seed migration may *additionally* exist for
fresh-deploy convenience, but it must call the **same** logic the CLI uses, not duplicate it.

**Open (deferred to deployment):**
- Password source in a no-TTY container (interactive prompt vs. `ADMIN_PASSWORD` env read
  once).
- Docker invocation (`docker compose run --rm`) and startup ordering (migrations → app →
  admin creation).
- Idempotency: re-running must not duplicate the user or reset a changed password.

---

## ADR-026: Relational/ownership permissions — deferred

**Status:** Open (deferred)

**Decision:** Defer "instructor may remove/invite only instructors **they** added." This is
**not** a flat `(role, permission)` capability — it depends on the *target* row's relationship
to the actor (e.g. `course_memberships.assigned_by == actor.id`), so it cannot live in
`role_permissions`/`course_membership_permissions`.

**Future approach (when needed):** add an `assigned_by` column to `course_memberships` and
handle these actions as an **ownership check inside `may()`** (or a sibling resolver) for the
specific actions, layered on top of the flat capability check. Structurally orthogonal to
ADR-022.

**Why deferred:** the flat model covers all launch needs; the ownership rule adds real
complexity for a narrow case.

---

## Vertical slice build plan (RBAC rollout)

The ADRs above are decisions; these slices are shippable increments. Mapping is many-to-many.
Build and test each slice before the next.

**Slice 0 — foundation (done).** `get_current_user` implemented (ADR-019, `api/dependencies.py`);
no escalation hole. Nothing to build.

**Slice 1 — admin spine.** `users.is_admin` column + migration · `create-admin` CLI ·
`require_admin` dependency · one guarded endpoint (e.g. `GET /admin/ping`).
*Verify (pytest):* admin → 200, normal user → 403; `is_admin` absent from
`UserCreate`/`UserUpdate`. *ADRs 020, 025; 024 (admin-short-circuit half).*

**Slice 2 — RBAC data model + seed.** `roles`, `permissions`, `role_permissions`,
`course_memberships(role_id)`, `course_membership_permissions` + migration · unique constraints
(`roles.name`, `permissions.code`, the two pair-keys, `(user_id, course_id)`) · seed migration
via natural-key lookups. *Verify:* fresh/test DB comes up with the vocabulary; seed is
reproducible. *ADRs 021, 022, 023.*

**Slice 3 — per-course enforcement.** `may()` resolver (merge, deny-wins) ·
`require_permission(action)` factory · apply to the first real protected course endpoint.
*Verify:* student blocked from write, instructor allowed, a `grant=false` override flips it.
*ADRs 022, 024.*

**Slice 4 — admin panel CRUD.** Screens over memberships + overrides (and a read-only
role/permission catalog), each guarded by `require_admin`/`require_permission`. The panel is a
consequence of the model, not new authorization logic. *ADRs 020–024.*

**Deferred:** ownership rule (ADR-026); progress/enrollment host table after unification
(ADR-021 open sub-question); 403-vs-404 per resource (ADR-024 open).

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
8. Progress/enrollment host table after the ADR-021 unification (where per-user
   progress/completion/grades attach now that `enrollments` is gone) (ADR-021).
9. 403 vs 404 existence-hiding, per sensitive resource (ADR-024).
10. Relational/ownership permissions — "only instructors you added" — deferred (ADR-026).
11. Admin-bootstrap deployment details: password source in a no-TTY container, Docker
    invocation, startup ordering, idempotency (ADR-025).
12. `may()` per-request permission caching, once read volume justifies it (ADR-024).
