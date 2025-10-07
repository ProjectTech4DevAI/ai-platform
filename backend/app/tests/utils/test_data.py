from sqlmodel import Session

from app.models import (
    Organization,
    Project,
    APIKey,
    APIKeyCreateResponse,
    Credential,
    OrganizationCreate,
    ProjectCreate,
    CredsCreate,
    FineTuningJobCreate,
    Fine_Tuning,
    ModelEvaluation,
    ModelEvaluationBase,
    ModelEvaluationStatus,
)
from app.crud import (
    create_organization,
    create_project,
    set_creds_for_org,
    create_fine_tuning_job,
    create_model_evaluation,
    APIKeyCrud,
)
from app.core.providers import Provider
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import (
    random_lower_string,
    generate_random_string,
    get_document,
    get_project,
)
from app.tests.utils.auth import TestAuthContext, get_auth_context


def create_test_organization(db: Session) -> Organization:
    """
    Creates and returns a test organization with a unique name.

    Persists the organization to the database.
    """
    name = f"TestOrg-{random_lower_string()}"
    org_in = OrganizationCreate(name=name, is_active=True)
    return create_organization(session=db, org_create=org_in)


def create_test_project(db: Session) -> Project:
    """
    Creates and returns a test project under a newly created test organization.

    Persists both the organization and the project to the database.

    """
    org = create_test_organization(db)
    name = f"TestProject-{random_lower_string()}"
    project_description = "This is a test project description."
    project_in = ProjectCreate(
        name=name,
        description=project_description,
        is_active=True,
        organization_id=org.id,
    )
    return create_project(session=db, project_create=project_in)


def test_credential_data(db: Session) -> CredsCreate:
    """
    Returns credential data for a test project in the form of a CredsCreate schema.

    Use this when you just need credential input data without persisting it to the database.
    """
    project = create_test_project(db)
    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    return creds_data


def create_test_api_key(
    db: Session,
    project_id: int | None = None,
    user_id: int | None = None,
) -> APIKeyCreateResponse:
    """
    Creates and returns a test API key for a specific project and user.

    Persists the API key to the database.
    """
    if user_id is None:
        user = create_random_user(db)
        user_id = user.id

    if project_id is None:
        project = create_test_project(db)
        project_id = project.id

    api_key_crud = APIKeyCrud(session=db, project_id=project_id)
    raw_key, api_key = api_key_crud.create(user_id=user_id, project_id=project_id)
    return APIKeyCreateResponse(key=raw_key, **api_key.dict())


def create_test_credential(db: Session) -> tuple[list[Credential], Project]:
    """
    Creates and returns a test credential for a test project.

    Persists the organization, project, and credential to the database.

    """
    project = create_test_project(db)
    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    return (
        set_creds_for_org(
            session=db,
            creds_add=creds_data,
            organization_id=project.organization_id,
            project_id=project.id,
        ),
        project,
    )


def create_test_fine_tuning_jobs(
    db: Session,
    ratios: list[float],
) -> tuple[list[Fine_Tuning], bool]:
    project = get_project(db, "Dalgo")
    document = get_document(db, "dalgo_sample.json")
    jobs = []
    any_created = False

    for ratio in ratios:
        job_request = FineTuningJobCreate(
            document_id=document.id,
            base_model="gpt-4",
            split_ratio=[ratio],
            system_prompt="str",
        )
        job, created = create_fine_tuning_job(
            session=db,
            request=job_request,
            split_ratio=ratio,
            project_id=project.id,
            organization_id=project.organization_id,
        )
        jobs.append(job)
        if created:
            any_created = True

    return jobs, any_created


def create_test_finetuning_job_with_extra_fields(
    db: Session,
    ratios: list[float],
) -> tuple[list[Fine_Tuning], bool]:
    jobs, _ = create_test_fine_tuning_jobs(db, ratios)

    if jobs:
        for job in jobs:
            job.test_data_s3_object = "test_data_s3_object_example"
            job.fine_tuned_model = "fine_tuned_model_name"

    return jobs, True


def create_test_model_evaluation(db) -> list[ModelEvaluation]:
    fine_tune_jobs, _ = create_test_finetuning_job_with_extra_fields(db, [0.5, 0.7])

    model_evaluations = []

    for fine_tune in fine_tune_jobs:
        request = ModelEvaluationBase(
            fine_tuning_id=fine_tune.id,
            system_prompt=fine_tune.system_prompt,
            base_model=fine_tune.base_model,
            fine_tuned_model=fine_tune.fine_tuned_model,
            document_id=fine_tune.document_id,
            test_data_s3_object=fine_tune.test_data_s3_object,
        )

        model_eval = create_model_evaluation(
            session=db,
            request=request,
            project_id=fine_tune.project_id,
            organization_id=fine_tune.organization_id,
            status=ModelEvaluationStatus.pending,
        )

        model_evaluations.append(model_eval)

    return model_evaluations
