from fastcrud import FastCRUD
from ..models.prompt import Prompt
from ..schemas.prompt import PromptCreateInternal, PromptUpdate, PromptUpdateInternal, PromptDelete

CRUDPrompt = FastCRUD[Prompt, PromptCreateInternal, PromptUpdate, PromptUpdateInternal, PromptDelete]
crud_prompts = CRUDPrompt(Prompt)
