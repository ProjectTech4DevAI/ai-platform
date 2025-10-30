from sqlmodel import Field, SQLModel
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class AuthContext(SQLModel):
    user: User
    organization: Organization | None = None
    project: Project | None = None
