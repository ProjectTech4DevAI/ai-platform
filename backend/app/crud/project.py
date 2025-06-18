import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import HTTPException

from app.models import Project, ProjectCreate, Organization
from app.core.util import now

logger = logging.getLogger(__name__)


def create_project(*, session: Session, project_create: ProjectCreate) -> Project:
    logger.info(
        f"[create_project] Starting project creation | {{'name': '{project_create.name}', 'org_id': {project_create.organization_id}}}"
    )
    db_project = Project.model_validate(project_create)
    db_project.inserted_at = now()
    db_project.updated_at = now()
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    logger.info(
        f"[create_project] Project created successfully | {{'project_id': {db_project.id}, 'name': '{db_project.name}', 'org_id': {db_project.organization_id}}}"
    )
    return db_project


def get_project_by_id(*, session: Session, project_id: int) -> Optional[Project]:
    logger.info(
        f"[get_project_by_id] Retrieving project | {{'project_id': {project_id}}}"
    )
    statement = select(Project).where(Project.id == project_id)
    project = session.exec(statement).first()
    if project:
        logger.info(
            f"[get_project_by_id] Project retrieved successfully | {{'project_id': {project_id}, 'name': '{project.name}'}}"
        )
    else:
        logger.warning(
            f"[get_project_by_id] Project not found | {{'project_id': {project_id}}}"
        )
    return project


def get_projects_by_organization(*, session: Session, org_id: int) -> List[Project]:
    logger.info(
        f"[get_projects_by_organization] Retrieving projects for organization | {{'org_id': {org_id}}}"
    )
    statement = select(Project).where(Project.organization_id == org_id)
    projects = session.exec(statement).all()
    logger.info(
        f"[get_projects_by_organization] Projects retrieved successfully | {{'org_id': {org_id}, 'project_count': {len(projects)}}}"
    )
    return projects


def validate_project(session: Session, project_id: int) -> Project:
    """
    Ensures that an project exists and is active.
    """
    logger.info(
        f"[validate_project] Validating project | {{'project_id': {project_id}}}"
    )
    project = get_project_by_id(session=session, project_id=project_id)
    if not project:
        logger.warning(
            f"[validate_project] Project not found | {{'project_id': {project_id}}}"
        )
        raise HTTPException(404, "Project not found")

    if not project.is_active:
        logger.warning(
            f"[validate_project] Project is not active | {{'project_id': {project_id}, 'name': '{project.name}'}}"
        )
        raise HTTPException(404, "Project is not active")

    logger.info(
        f"[validate_project] Project validated successfully | {{'project_id': {project_id}, 'name': '{project.name}'}}"
    )
    return project