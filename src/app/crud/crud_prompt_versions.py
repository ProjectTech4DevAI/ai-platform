from fastcrud import FastCRUD
from ..models.prompt_version import PromptVersion
from ..schemas.prompt_version import PromptVersionCreateInternal, PromptVersionUpdate, PromptVersionUpdateInternal, PromptVersionDelete

CRUDPromptVersion = FastCRUD[PromptVersion, PromptVersionCreateInternal, PromptVersionUpdate, PromptVersionUpdateInternal, PromptVersionDelete]
crud_prompt_versions = CRUDPromptVersion(PromptVersion)
