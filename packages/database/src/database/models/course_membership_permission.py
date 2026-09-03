from sqlalchemy import BigInteger, ForeignKey, Identity, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class CourseMembershipPermission(Base):
    __tablename__ = "course_membership_permissions"
    __table_args__ = (UniqueConstraint("course_membership_id", "permission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    course_membership_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("course_memberships.id"), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id"), nullable=False
    )
    grant: Mapped[bool] = mapped_column(nullable=False)
