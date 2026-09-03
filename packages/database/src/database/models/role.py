from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base

ROLE_NAME_LENGTH = 16


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(ROLE_NAME_LENGTH), unique=True)
