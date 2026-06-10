from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from database.constants import SESSION_HASH_LENGTH
from database.models.user import User


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Deterministic digest (sha256 hex) of the raw token; the raw token lives
    # only in the cookie. Unique + indexed: it is the per-request lookup key.
    hash: Mapped[str] = mapped_column(String(SESSION_HASH_LENGTH), unique=True)

    # Expiry stored as events (ADR-019): created_at anchors the absolute ceiling,
    # last_seen_at anchors the idle window (lazily bumped). No updated_at /
    # SoftDeleteMixin -- logout and expiry are hard deletes.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
