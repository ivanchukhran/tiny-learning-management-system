from sqlalchemy import BigInteger, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from database.constants import (
    COURSE_DESCRIPTION_LENGTH,
    COURSE_NAME_LENGTH,
    COURSE_SLUG_LENGTH,
)


class Course(Base):
    __tablename__ = "courses"

    __table_args__ = (UniqueConstraint("name", "slug", name="uq_name_slug"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(COURSE_NAME_LENGTH))
    slug: Mapped[str] = mapped_column(String(COURSE_SLUG_LENGTH))
    description: Mapped[str] = mapped_column(String(COURSE_DESCRIPTION_LENGTH))
