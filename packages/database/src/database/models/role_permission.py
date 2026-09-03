from sqlalchemy import BigInteger, ForeignKey, Identity, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE")
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id", ondelete="CASCADE")
    )
