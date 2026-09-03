"""RBAC seed data and a reusable, idempotent seeding routine.

This module is the single source of truth for the RBAC vocabulary (role names,
permission codes) and the default role -> permission mapping. Guards and the
future ``may()`` resolver should reference these constants by name rather than
re-typing the strings.

``seed`` is intentionally **sync** and built on SQLAlchemy **Core** so the same
function serves both callers:
- the Alembic data migration: ``seed(op.get_bind())``
- the testcontainers fixtures: ``await conn.run_sync(seed)``

Rows are matched by their **natural key** (role name / permission code), never by
surrogate id (ADR-023), and existing rows are skipped so re-running is safe.
"""

from enum import StrEnum

from sqlalchemy import Connection, delete, insert, select

from database.models import Permission, Role, RolePermission

# --- Canonical vocabulary -----------------------------------------------------


class RoleName(StrEnum):
    """Per-course role names. Bounded set; members are stored verbatim in
    ``roles.name`` (StrEnum members are plain strings)."""

    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ASSISTANT = "assistant"


class PermissionCode(StrEnum):
    """Dotted ``<resource>.<action>`` permission codes, stored in
    ``permissions.code``. Generalizes later to ``memberships.*`` etc. Coarse for
    now: ``memberships.create`` gates creating a course_membership row;
    restricting *which* role may be assigned is deferred per ADR-026."""

    MEMBERSHIPS_CREATE = "memberships.create"


ROLE_DEFAULTS: dict[RoleName, tuple[PermissionCode, ...]] = {
    RoleName.INSTRUCTOR: (PermissionCode.MEMBERSHIPS_CREATE,),
}


# --- Seeding ------------------------------------------------------------------


def seed(connection: Connection) -> None:
    """Idempotently seed roles, permissions, then the role -> permission map.

    Order matters: the vocabulary rows must exist before role_permissions can
    reference them by natural key.
    """
    _seed_by_key(connection, Role, Role.name, RoleName)
    _seed_by_key(connection, Permission, Permission.code, PermissionCode)
    _seed_role_permissions(connection)


def unseed(connection: Connection) -> None:
    """Reverse ``seed`` by natural key (children before parents). Used by the
    migration downgrade. Fails loudly if a role/permission is still referenced
    by real data — that is the correct signal, not something to swallow.
    """
    role_id = dict(
        (name, id) for name, id in connection.execute(select(Role.name, Role.id)).all()
    )
    perm_id = dict(
        (code, id)
        for code, id in connection.execute(select(Permission.code, Permission.id)).all()
    )
    for role_name, codes in ROLE_DEFAULTS.items():
        for code in codes:
            if role_name in role_id and code in perm_id:
                connection.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id == role_id[role_name],
                        RolePermission.permission_id == perm_id[code],
                    )
                )
    connection.execute(
        delete(Permission).where(Permission.code.in_(list(PermissionCode)))
    )
    connection.execute(delete(Role).where(Role.name.in_(list(RoleName))))


def _seed_by_key(connection: Connection, model, key_column, values) -> None:
    key = key_column.key
    existing = set(connection.scalars(select(key_column)))
    rows = [{key: value} for value in values if value not in existing]
    if rows:
        connection.execute(insert(model), rows)


def _seed_role_permissions(connection: Connection) -> None:
    role_id = dict(
        (name, id) for name, id in connection.execute(select(Role.name, Role.id)).all()
    )
    perm_id = dict(
        (code, id)
        for code, id in connection.execute(select(Permission.code, Permission.id)).all()
    )
    existing = {
        tuple(row)
        for row in connection.execute(
            select(RolePermission.role_id, RolePermission.permission_id)
        )
    }
    rows = []
    for role_name, codes in ROLE_DEFAULTS.items():
        for code in codes:
            pair = (role_id[role_name], perm_id[code])
            if pair not in existing:
                rows.append({"role_id": pair[0], "permission_id": pair[1]})
    if rows:
        connection.execute(insert(RolePermission), rows)
