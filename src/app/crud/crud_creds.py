from fastcrud import FastCRUD

from ..models.credentials import Credentials
from ..schemas.credentials import (
    CredentialsCreateInternal,
    CredentialsDelete,
    CredentialsUpdate,
    CredentialsUpdateInternal,
    CredentialsRead,
)

CRUDCredentials = FastCRUD[
    Credentials,
    CredentialsCreateInternal,
    CredentialsUpdate,
    CredentialsUpdateInternal,
    CredentialsDelete,
    CredentialsRead,
]
crud_credentials = CRUDCredentials(Credentials)
