from datetime import datetime

from sqlalchemy import DateTime, event, func, orm
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def soft_delete(self):
        self.deleted_at = func.now()

    def restore(self):
        self.deleted_at = None


@event.listens_for(orm.Session, "do_orm_execute")
def _add_soft_delete_filter(execution_state: orm.ORMExecuteState) -> None:
    if execution_state.execution_options.get("include_deleted", False):
        return

    execution_state.statement = execution_state.statement.options(
        orm.with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at == None,  # noqa: E711
            include_aliases=True,
            propagate_to_loaders=True,
        )
    )
