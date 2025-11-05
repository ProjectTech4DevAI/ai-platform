import logging
from uuid import UUID

from sqlmodel import Session, select, and_, func
from fastapi import HTTPException

from .config import ConfigCrud
from app.core.util import now
from app.models import Config, ConfigVersion, ConfigVersionCreate

logger = logging.getLogger(__name__)


class ConfigVersionCrud:
    """
    CRUD operations for configuration versions scoped to a project.
    """

    def __init__(self, session: Session, config_id: UUID, project_id: int):
        self.session = session
        self.project_id = project_id
        self.config_id = config_id

    def create(self, version_create: ConfigVersionCreate) -> ConfigVersion:
        """
        Create a new version for an existing configuration.
        Automatically increments the version number.
        """
        self._config_exists(self.config_id)
        try:
            next_version = self._get_next_version(self.config_id)

            # Create the new version
            version = ConfigVersion(
                config_id=self.config_id,
                version=next_version,
                config_json=version_create.config_json,
                commit_message=version_create.commit_message,
            )

            self.session.add(version)
            self.session.commit()
            self.session.refresh(version)

            logger.info(
                f"[ConfigVersionCrud.create] Version created successfully | "
                f"{{'config_id': '{self.config_id}', 'version_id': '{version.id}'}}"
            )

            return version

        except Exception as e:
            self.session.rollback()
            logger.error(
                f"[ConfigVersionCrud.create] Failed to create version | "
                f"{{'config_id': '{self.config_id}', 'error': '{str(e)}'}}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Unexpected error occurred: failed to create version",
            )

    def read_one(self, version_id: UUID) -> ConfigVersion | None:
        """
        Read a specific configuration version by its ID.
        """
        self._config_exists(self.config_id)
        statement = select(ConfigVersion).where(
            and_(
                ConfigVersion.id == version_id,
                ConfigVersion.config_id == self.config_id,
                ConfigVersion.deleted_at.is_(None),
            )
        )
        return self.session.exec(statement).one_or_none()

    def read_all(self, skip: int = 0, limit: int = 100) -> list[ConfigVersion]:
        """
        Read all versions for a specific configuration with pagination.
        """
        self._config_exists(self.config_id)
        statement = (
            select(ConfigVersion)
            .where(
                and_(
                    ConfigVersion.config_id == self.config_id,
                    ConfigVersion.deleted_at.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return self.session.exec(statement).all()

    def delete(self, version_id: UUID) -> None:
        """
        Soft delete a configuration version by setting its deleted_at timestamp.
        """
        version = self.read_one(version_id)
        if version is None:
            raise HTTPException(
                status_code=404,
                detail=f"Version with id '{version_id}' not found'",
            )

        version.deleted_at = now()
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

    def _get_next_version(self, config_id: UUID) -> int | None:
        """Get the next version number for a config."""
        statement = select(func.max(ConfigVersion.version)).where(
            and_(
                ConfigVersion.config_id == config_id,
            )
        )
        return self.session.exec(statement).one() + 1

    def _config_exists(self, config_id: UUID) -> Config:
        """Check if a config exists in the project."""
        config_crud = ConfigCrud(session=self.session, project_id=self.project_id)
        config = config_crud.read_one(config_id)

        if config is None:
            raise HTTPException(
                status_code=404,
                detail=f"Config with id '{config_id}' not found in this project",
            )
        return config
