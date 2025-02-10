import uuid
import functools as ft
from pathlib import Path
from datetime import datetime
from urllib.parse import ParseResult, urlparse, urlunparse

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from ..core.db.database import Base

#
#
#
class MyTypeDecorator(TypeDecorator):
    impl = String

    @ft.singledispatchmethod
    def process_bind_param(self, value, dialect):
        return None

    @process_bind_param.register
    def _(self, value: str, dialect):
        return value

    @process_bind_param.register
    def _(self, value: ParseResult, dialect):
        return self.to_string(value)

    def process_literal_param(self, value, dialect):
        param = self.process_bind_param(value, dialect)
        return 'NULL' if param is None else f"'{param}'"

    def process_result_value(self, value, dialect):
        return None if value is None else self.from_string(value)

    def to_string(self, value):
        raise NotImplementedError()

    def from_string(self, value):
        raise NotImplementedError()

class URLType(MyTypeDecorator):
    @property
    def python_type(self):
        return ParseResult

    def to_string(self, value):
        return urlunparse(value)

    def from_string(self, value):
        return urlparse(value)

class PathType(MyTypeDecorator):
    @property
    def python_type(self):
        return Path

    def to_string(self, value):
        return str(value)

    def from_string(self, value):
        return self.python_type(value)

#
#
#
class Document(Base):
    __tablename__ = "document"

    #
    # Keys
    #
    id: Mapped[int] = mapped_column(
        "id",
        autoincrement=True,
        nullable=False,
        unique=True,
        primary_key=True,
        init=False,
    )
    owner: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), # XXX Does user correspond to client-project?
        index=True,
        default=None,
        init=False,
    )

    #
    # Data representation
    #
    fname_internal: Mapped[uuid.UUID] = mapped_column(
        default_factory=uuid.uuid4,
        primary_key=True,
        unique=True,
    )
    fname_external: Mapped[Path] = mapped_column(PathType)
    object_store_url: Mapped[ParseResult] = mapped_column(URLType)

    #
    # Record management
    #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=datetime.utcnow,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
