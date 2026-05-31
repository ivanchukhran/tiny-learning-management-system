# Design Discussions

Companion to [`decisions.md`](./decisions.md). Where the decision log records *what* was
decided, this document preserves the *discussion* behind each choice: the alternatives we
weighed, the concrete examples we used, and the diagrams drawn along the way. Useful for
revisiting a decision later and remembering why the road not taken was rejected.

Cross-references point to the matching `ADR-NNN` in the decision log.

---

## Entity map (working ERD)

The text ERD we used as the shared mental model. Two separate user↔course links
(`course_memberships` for authority, `enrollments` for consumption) are the backbone —
see ADR-003.

```
                       ┌─────────┐
                       │  User   │
                       └────┬────┘
                            │ M:N
                ┌───────────┼──────────────┐
                │           │              │
         ┌──────▼─────┐ ┌───▼──────────┐ ┌─▼──────────┐
         │   Group    │ │ CourseMember │ │ Enrollment │
         │            │ │  (role per   │ │ (student   │
         │            │ │   course)    │ │  access)   │
         └──────┬─────┘ └───┬──────────┘ └─┬──────────┘
                │           │              │
                │           │              │
                │      ┌────▼──────────────▼───┐
                └─────▶│       Course          │
                       └────────────┬──────────┘
                                    │ 1:N (ordered)
                              ┌─────▼─────┐
                              │   Topic   │
                              └─────┬─────┘
                                    │ 1:N (ordered)
                              ┌─────▼─────┐         ┌──────────────┐
                              │   Post    │◀────────│ Assignment   │
                              │ (lesson)  │         │ (topic_id    │
                              └─────┬─────┘         │  nullable)   │
                                    │ 1:N           └──────┬───────┘
                              ┌─────▼─────────┐            │ 1:N
                              │  ContentItem  │      ┌─────▼──────┐
                              │  kind=file|   │      │ Submission │
                              │       url|    │      └─────┬──────┘
                              │       video   │            │
                              └───────────────┘      ┌─────▼─────┐
                                                     │   Grade   │
                                                     └───────────┘
```

Key observations from the discussion:

- **Two different user↔course relationships exist.** `course_memberships` (who can
  teach/manage) vs. `enrollments` (who is taking it as a student). Conflating them is the
  #1 LMS modeling mistake. (→ ADR-003)
- **Group sits sideways, not in the middle.** A group is a reusable bundle of users. When
  you "enroll a group," you really create N enrollment rows (→ ADR-004, materialized). The
  Group entity itself doesn't own access; it's a convenience for bulk operations.
- **Topic and Post both need ordering** — a recurring design problem (see "Ordering
  pattern" below), not a free column.

---

## Discussion 1 — Group enrollment semantics (→ ADR-004)

**Scenario.** Group "CS-101 Fall 2026" (30 students) is enrolled in course "Intro to
Python." Mid-semester, Alice joins the group. Does she automatically get course access?

### Approach A — "Live link" (lazy resolution)
Store **one** row: `Enrollment(group_id=CS-101, course_id=Python)`. Access is computed
on the fly: "Can Alice see Python? → her groups → CS-101 → CS-101 enrolled in Python → yes."

- Alice joins group → instantly gains access. No extra work.
- Alice removed → instantly loses access.
- ✗ Cannot give Alice an individual enrollment status (finished early, withdrawn) without
  special-casing.

### Approach B — "Materialized" (eager expansion) ✅ chosen
Enrolling the group creates **30 individual rows**:
`Enrollment(user_id=Bob, course_id=Python, source='group:CS-101')`, etc.

- Alice joins group → a job creates her enrollment row (must not forget).
- Alice removed → her row can stay (preserve progress/grades) or be removed — our choice.
- ✓ Each user gets their own enrollment lifecycle: status, completion date, certificate,
  withdrawal, individual grade.

**One-line trade-off.** A is simpler and always-correct for access checks but loses
individuality; B is more maintenance but gives each user an independent enrollment
lifecycle.

**Why B won.** LMSes always end up needing per-user enrollment state. Approach A is
regretted within a month. We keep `source` so we remember where an enrollment came from.

---

## Discussion 2 — Assignment placement (→ ADR-005)

Course "Intro to Python", topics: `1. Variables`, `2. Loops`, `3. Functions`.

- **Topic-level**: assignment belongs to one topic ("Write a FizzBuzz loop" under Loops).
  Appears in context, natural progression.
- **Course-level**: assignment belongs to the whole course ("Final project", "Midterm").
  Cross-cutting work that doesn't fit one topic.

**Resolution: support both** via a nullable `topic_id` on `assignments`, with `course_id`
always required:
- `topic_id = 5` → topic-level (shows under that topic)
- `topic_id = NULL` → course-level (shows under the course)

This is what Moodle/Canvas do.

---

## Discussion 3 — Progress tracking (→ ADR-011)

**Agreed granularity.** Track progress across all activities. Two completion mechanisms:
- **Implicit / auto** — video auto-completes when played to the end.
- **Explicit** — a post is completed when the user clicks "mark as completed."

Several sub-debates were opened and **left open** (recorded here so we don't lose the
framing):

### 3a — Events vs. State vs. Both

**Option 1 — State only.** One row per (user, thing), overwritten on update.
```
ProgressState(user_id, trackable_type, trackable_id, status,
              progress_value, completed_at, updated_at)
```
+ Simple, fast "is this done?", small table.
− No history; can't answer "when did they first watch?"; can't recompute if rules change.

**Option 2 — Event log only.** Append-only; current state folded from events.
```
ProgressEvent(id, user_id, trackable_type, trackable_id, event_type,
              payload JSONB, occurred_at)
```
+ Full audit trail; analytics; replayable when completion rules change.
− "Is this done?" requires scanning events; table grows fast.

**Option 3 — Both.** Append events *and* maintain a projected state row.
+ Fast reads and full history; state rebuildable from events.
− Two writes per update; risk of drift (mitigated by rebuild-from-events).

**Driving question (unresolved):** if a teacher changes "video must reach 100%" to "90%"
and you want to retroactively re-evaluate everyone, which options make that possible?
(Answer: the ones that keep events — Option 2 or 3.)

### 3b — Polymorphic trackable

A user can complete a ContentItem, Post, Topic, Course, or Assignment — five tables, one
progress system. How to model the FK?

- **Approach A — Polymorphic association** (`trackable_type` + `trackable_id`). One
  progress table for everything. ✗ No DB-level FK integrity (Postgres can't verify
  `trackable_id` exists in the right table); dangling rows possible.
- **Approach B — Separate progress tables per activity.** Real FKs, full integrity. ✗ 4–5
  near-identical tables; generic "all progress" queries are harder.
- **Approach C — Supertype `activity` table** all trackables inherit from; progress FKs to
  it. ✓ Integrity + single progress table. ✗ Extra join everywhere, more migration work.

Most FastAPI/SQLAlchemy projects pick **A** for pragmatism (we already soft-delete, so the
dangle risk is small). **Not yet decided.**

### 3c — Video completion subtleties
Users scrub to the end. Decisions still open: track **furthest position** (allows
skipping) vs. **cumulative seconds watched** (anti-skip); completion rule ("≥95%",
"linear order", `ended` event); heartbeat frequency; resume-on-reload. Research terms:
*video heartbeats, watch-time analytics, resume position.*

### 3d — Post completion subtleties
Open questions: can a post with zero content items be completed? If all its items
auto-complete, is the post auto-complete or does the button still apply? Can a user
*un-complete* (toggle) a post — delete the row or null `completed_at`?

### 3e — Completion bubbling ("Topic 2: 4/7 complete", "Course 47%")
- **On-the-fly** (aggregate at read time): always accurate, no state to drift; expensive
  at scale.
- **Denormalized counters** (`TopicProgress.completed_count/total_count`): single-row
  read; must invalidate on add/remove/soft-delete, easy to drift.

**Guidance:** start on-the-fly; denormalize only when a real perf problem is measured.
Premature denormalization is a top source of "5/7 complete" bugs.

### Sharp edge-case questions (raised, unresolved)
- New post added to an already-"completed" topic — do students drop to 6/7? Notified?
  Does it not apply to them?
- Post soft-deleted — what happens to existing completion records and percentages?
- Watch 30%, leave, watch a different 30% — is that 60% or 30%? (cumulative vs furthest)
- Should progress survive un-enrollment and re-enrollment?

---

## Patterns flagged for research (not yet implemented)

These came up as "things you'll need to handle" and are parked for when the relevant
models are built.

### Ordering / sortable lists (Topics, Posts)
Reordering a list (drag item 5 between 1 and 2) is non-trivial. Options:
- Plain integer `position` (simple; renumber on insert).
- Sparse integers (100, 200, 300 — insert at 150).
- Fractional / lexorank strings (what Jira/Trello use).

Open trade-off: optimize for fast reads, fast reorders, or simple code?

### ContentItem shape (→ ADR-006)
- Single table + nullable columns (`kind`, `file_id?`, `external_url?`) — simple,
  app-level invariants.
- Single table + `payload JSONB` per kind — Postgres-friendly, extensible (add "quiz"
  with zero migrations).
- Joined-table inheritance — pure, but verbose, more joins.

### Soft delete enforcement (→ ADR-007)
`deleted_at` is the easy part. Hard parts: cascading (soft-delete a Topic → its
Posts/Assignments?), unique-constraint reuse (does a deleted slug block reuse?), and the
global read filter (`WHERE deleted_at IS NULL` everywhere — SQLAlchemy options:
`with_loader_criteria`, query event hooks, base-mixin helper).

### Authorization ("can Alice edit Topic X?")
With per-course roles + co-teaching:
`Topic X → its Course → CourseMembership(Alice, that course) → role ∈ {instructor, admin}?`
FastAPI options: a `require_course_role(role)` dependency, or a policy module of pure
`can_edit_topic(user, topic) -> bool` functions. Research: RBAC vs ABAC, how Casbin/oso
shape the problem.

### N+1 queries
FastAPI + SQLAlchemy + careless code = death by 1000 queries. Research: `selectinload` vs
`joinedload`; when to denormalize a counter vs compute on the fly; read-models /
materialized views.

---

## Recommended pre-implementation exercises (from the discussion)

Before building more models, draft on paper:

1. **Complete ERD** — every table, column, FK, unique constraint, column type
   (`varchar(255)` vs `text` vs `citext` is a real decision).
2. **The "hard query" list** — write the 5–10 queries the app must do fast, in English
   then SQL. Schema follows queries, not the other way around. Examples:
   - "List all courses Alice is enrolled in, with progress %."
   - "For Course X, list topics with their posts and assignment counts."
   - "Find all ungraded submissions for instructor Bob."
3. **Migration strategy** — Alembic; understand schema vs data migrations *before* there's
   production data to break.

---

## Working style (meta)

The user is using this project to gain experience, so the default mode is: **the user
implements, Claude guides and reviews.** Claude provides patterns, alternatives, and traps
to research; writes code only on explicit request (and otherwise makes minimal mechanical
edits). Modes can be switched per task (fully guided, fully written, or hybrid where Claude
scaffolds boilerplate and the user writes the parts that matter for learning).
