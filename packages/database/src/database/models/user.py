from sqlalchemy import BigInteger, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from database.constants import (
    EMAIL_MAX_LENGTH,
    FIRST_NAME_MAX_LENGTH,
    LAST_NAME_MAX_LENGTH,
)
from database.models.mixins import SoftDeleteMixin, TimestampMixin


class User(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(FIRST_NAME_MAX_LENGTH))
    last_name: Mapped[str] = mapped_column(String(LAST_NAME_MAX_LENGTH))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
