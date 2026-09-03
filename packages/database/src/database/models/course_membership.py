from sqlalchemy import BigInteger, ForeignKey, Identity, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class CourseMembership(Base):
    __tablename__ = "course_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.id"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id"), nullable=False
    )
