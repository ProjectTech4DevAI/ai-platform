from sqlmodel import SQLModel, Field
from typing import Optional

class Prompt(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True) 