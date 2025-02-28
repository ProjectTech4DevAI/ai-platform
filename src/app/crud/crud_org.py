from fastcrud import FastCRUD


from ..models.organization import Organization
from ..schemas.organization import (
    OrganizationCreateInternal,
    OrganizationDelete,
    OrganizationUpdate,
    OrganizationUpdateInternal,
    OrganizationRead,
)

CRUDOrganization = FastCRUD[
    Organization,
    OrganizationCreateInternal,
    OrganizationUpdate,
    OrganizationUpdateInternal,
    OrganizationDelete,
    OrganizationRead,
]
crud_organizations = CRUDOrganization(Organization)
