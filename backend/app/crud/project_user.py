import logging
from sqlmodel import Session, select, delete, func
from app.models import ProjectUser, ProjectUserPublic, User, Project
from datetime import datetime, timezone

from app.core.util import now

logger = logging.getLogger(__name__)


def is_project_admin(session: Session, user_id: int, project_id: int) -> bool:
    """
    Checks if a user is an admin of the given project.
    """
    logger.info(
        f"[is_project_admin] Checking admin status | {{'user_id': {user_id}, 'project_id': {project_id}}}"
    )
    project_user = session.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == user_id,
            ProjectUser.is_deleted == False,
        )
    ).first()

    is_admin = bool(project_user and project_user.is_admin)
    logger.info(
        f"[is_project_admin] Admin check completed | {{'user_id': {user_id}, 'project_id': {project_id}, 'is_admin': {is_admin}}}"
    )
    return is_admin


def add_user_to_project(
    session: Session, project_id: int, user_id: int, is_admin: bool = False
) -> ProjectUserPublic:
    """
    Adds a user to a project.
    """
    logger.info(
        f"[add_user_to_project] Starting user addition to project | {{'user_id': {user_id}, 'project_id': {project_id}, 'is_admin': {is_admin}}}"
    )
    existing = session.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project_id, ProjectUser.user_id == user_id
        )
    ).first()

    if existing:
        logger.warning(
            f"[add_user_to_project] User already a member | {{'user_id': {user_id}, 'project_id': {project_id}}}"
        )
        raise ValueError("User is already a member of this project.")

    project_user = ProjectUser(
        project_id=project_id, user_id=user_id, is_admin=is_admin
    )
    session.add(project_user)
    session.commit()
    session.refresh(project_user)
    logger.info(
        f"[add_user_to_project] User added to project successfully | {{'user_id': {user_id}, 'project_id': {project_id}, 'is_admin': {is_admin}}}"
    )

    return ProjectUserPublic.model_validate(project_user)


def remove_user_from_project(session: Session, project_id: int, user_id: int) -> None:
    """
    Removes a user from a project.
    """
    logger.info(
        f"[remove_user_from_project] Starting user removal from project | {{'user_id': {user_id}, 'project_id': {project_id}}}"
    )
    project_user = session.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == user_id,
            ProjectUser.is_deleted == False,
        )
    ).first()
    if not project_user:
        logger.warning(
            f"[remove_user_from_project] User not a member or already removed | {{'user_id': {user_id}, 'project_id': {project_id}}}"
        )
        raise ValueError("User is not a member of this project or already removed.")

    project_user.is_deleted = True
    project_user.deleted_at = now()
    session.add(project_user)
    session.commit()
    logger.info(
        f"[remove_user_from_project] User removed from project successfully | {{'user_id': {user_id}, 'project_id': {project_id}}}"
    )


def get_users_by_project(
    session: Session, project_id: int, skip: int = 0, limit: int = 100
) -> tuple[list[ProjectUserPublic], int]:
    """
    Returns paginated users in a given project along with the total count.
    """
    logger.info(
        f"[get_users_by_project] Retrieving users for project | {{'project_id': {project_id}, 'skip': {skip}, 'limit': {limit}}}"
    )
    count_statement = (
        select(func.count())
        .select_from(ProjectUser)
        .where(ProjectUser.project_id == project_id, ProjectUser.is_deleted == False)
    )
    total_count = session.exec(count_statement).one()
    logger.info(
        f"[get_users_by_project] Total user count retrieved | {{'project_id': {project_id}, 'total_count': {total_count}}}"
    )

    statement = (
        select(ProjectUser)
        .where(ProjectUser.project_id == project_id, ProjectUser.is_deleted == False)
        .offset(skip)
        .limit(limit)
    )
    users = session.exec(statement).all()
    logger.info(
        f"[get_users_by_project] Users retrieved successfully | {{'project_id': {project_id}, 'user_count': {len(users)}}}"
    )

    return [ProjectUserPublic.model_validate(user) for user in users], total_count


def is_user_part_of_organization(session: Session, user_id: int, org_id: int) -> bool:
    """
    Checks if a user is part of at least one project within the organization.
    """
    logger.info(
        f"[is_user_part_of_organization] Checking user membership in organization | {{'user_id': {user_id}, 'org_id': {org_id}}}"
    )
    user_in_org = session.exec(
        select(ProjectUser)
        .join(Project, ProjectUser.project_id == Project.id)
        .where(
            Project.organization_id == org_id,
            ProjectUser.user_id == user_id,
            ProjectUser.is_deleted == False,
        )
    ).first()

    is_member = bool(user_in_org)
    logger.info(
        f"[is_user_part_of_organization] Membership check completed | {{'user_id': {user_id}, 'org_id': {org_id}, 'is_member': {is_member}}}"
    )
    return is_member
