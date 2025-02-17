# Delete once organization and project schema are setup
from pydantic import BaseModel


class ProjectRead(BaseModel):
    id: int
    
    
class OrganizationRead(BaseModel):
    id: int