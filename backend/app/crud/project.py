from sqlmodel import Session, select

from app.models import Project, ProjectCreate


def create_project(*, session: Session, project_create: ProjectCreate) -> Project:
    db_project = Project.model_validate(project_create)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


def get_project_by_id(*, session: Session, project_id: int) -> Project | None:
    statement = select(Project).where(Project.id == project_id)
    return session.exec(statement).first()


def get_projects_by_organization(*, session: Session, org_id: int) -> list[Project]:
    statement = select(Project).where(Project.organization_id == org_id)
    return session.exec(statement).all()
