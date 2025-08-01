from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

# Configure connection pool settings
# For testing, we need more connections since tests run in parallel
pool_size = 20 if settings.ENVIRONMENT == "local" else 5
max_overflow = 30 if settings.ENVIRONMENT == "local" else 10

engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_size=pool_size,
    max_overflow=max_overflow,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections after 5 minutes
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
