import logging
from uuid import UUID
from typing import Tuple

from sqlmodel import Session, select, and_
from fastapi import HTTPException

from app.models import (
    Config,
    ConfigCreate,
    ConfigUpdate,
    ConfigVersion,
)
from app.crud.project import get_project_by_id
from app.core.util import now

logger = logging.getLogger(__name__)


class ConfigCrud:
    """
    CRUD operations for configurations scoped to a project.
    """

    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def create(self, config_create: ConfigCreate) -> Tuple[Config, ConfigVersion]:
        """
        Create a new configuration with an initial version.
        """
        existing = self._get_by_name(config_create.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Configuration with name '{config_create.name}' already exists in this project",
            )

        try:
            config = Config(
                name=config_create.name,
                description=config_create.description,
                project_id=self.project_id,
            )

            self.session.add(config)
            self.session.flush()  # Flush to get the config.id

            # Create the initial version
            version = ConfigVersion(
                config_id=config.id,
                version=1,
                config_json=config_create.config_json,
                commit_message=config_create.commit_message,
            )

            self.session.add(version)
            self.session.commit()
            self.session.refresh(config)
            self.session.refresh(version)

            logger.info(
                f"[ConfigCrud.create] Configuration created successfully | "
                f"{{'config_id': '{config.id}', 'config_version_id': '{version.id}', 'project_id': {self.project_id}}}"
            )

            return config, version

        except Exception as e:
            self.session.rollback()
            logger.error(
                f"[ConfigCrud.create] Failed to create configuration | "
                f"{{'name': '{config_create.name}', 'project_id': {self.project_id}, 'error': '{str(e)}'}}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail=f"Unexpected error occurred: failed to create config"
            )

    def _get_by_name(self, name: str) -> Config | None:
        statement = select(Config).where(
            and_(
                Config.name == name,
                Config.project_id == self.project_id,
                Config.deleted_at.is_(None),
            )
        )
        return self.session.exec(statement).one_or_none()
