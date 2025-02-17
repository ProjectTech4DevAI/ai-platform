from sqlalchemy.orm import Mapped, mapped_column
from ..core.db.database import Base
import uuid as uuid_pkg


# This is placeholder because not implemented at; will be removed soon
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)