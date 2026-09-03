"""seed rbac defaults

Revision ID: 98476e527e95
Revises: 7a330c5c9791
Create Date: 2026-06-24 00:00:33.848031

"""

from typing import Sequence, Union

from database.seed import seed, unseed

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98476e527e95"
down_revision: Union[str, Sequence[str], None] = "7a330c5c9791"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed RBAC vocabulary and the default role->permission mapping."""
    seed(op.get_bind())


def downgrade() -> None:
    """Remove the seeded RBAC vocabulary and defaults."""
    unseed(op.get_bind())
