"""create course tables

Revision ID: 7a330c5c9791
Revises: d0ab01229619
Create Date: 2026-06-23 00:20:19.366362

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a330c5c9791"
down_revision: Union[str, Sequence[str], None] = "d0ab01229619"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "courses",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False, start=1), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("name", "slug", name="uq_name_slug"),
    )
    op.create_table(
        "course_memberships",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_course_memberships_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_course_memberships_course_id_courses"),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_course_memberships_role_id_roles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_memberships")),
        sa.UniqueConstraint(
            "user_id",
            "course_id",
            name=op.f("uq_course_memberships_user_id"),
        ),
    )
    op.create_table(
        "course_membership_permissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("course_membership_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.Column("grant", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_membership_id"],
            ["course_memberships.id"],
            name=op.f(
                "fk_course_membership_permissions_course_membership_id_course_memberships"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_course_membership_permissions_permission_id_permissions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_membership_permissions")),
        sa.UniqueConstraint(
            "course_membership_id",
            "permission_id",
            name=op.f("uq_course_membership_permissions_course_membership_id"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("course_membership_permissions")
    op.drop_table("course_memberships")
    op.drop_table("courses")
