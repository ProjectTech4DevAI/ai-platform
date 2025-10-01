import enum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any, List, Optional
from dataclasses import dataclass, field, fields

from sqlmodel import Field, Relationship, SQLModel
from pydantic import HttpUrl, BaseModel

from app.core.util import now
from .organization import Organization
from .project import Project
from app.core.util import now


class Collection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        ondelete="CASCADE",
    )

    project_id: int = Field(
        foreign_key="project.id",
        nullable=False,
        ondelete="CASCADE",
    )

    llm_service_id: Optional[str] = Field(default=None, nullable=True)
    llm_service_name: Optional[str] = Field(default=None, nullable=True)

    inserted_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    deleted_at: Optional[datetime] = None

    organization: Organization = Relationship(back_populates="collections")
    project: Project = Relationship(back_populates="collections")


@dataclass
class ResponsePayload:
    status: str
    route: str
    key: str = field(default_factory=lambda: str(uuid4()))
    time: str = field(default_factory=lambda: now().strftime("%c"))

    @classmethod
    def now(cls):
        attr = "time"
        for i in fields(cls):
            if i.name == attr:
                return i.default_factory()

        raise AttributeError(f'Expected attribute "{attr}" does not exist')


# pydantic models -
class DocumentOptions(BaseModel):
    documents: List[UUID] = Field(
        description="List of document IDs",
    )
    batch_size: int = Field(
        default=1,
        description=(
            "Number of documents to send to OpenAI in a single "
            "transaction. See the `file_ids` parameter in the "
            "vector store [create batch](https://platform.openai.com/docs/api-reference/vector-stores-file-batches/createBatch)."
        ),
    )

    def model_post_init(self, __context: Any):
        self.documents = list(set(self.documents))


class AssistantOptions(BaseModel):
    # Fields to be passed along to OpenAI. They must be a subset of
    # parameters accepted by the OpenAI.clien.beta.assistants.create
    # API.
    model: str = Field(
        description=(
            "OpenAI model to attach to this assistant. The model "
            "must compatable with the assistants API; see the "
            "OpenAI [model documentation](https://platform.openai.com/docs/models/compare) for more."
        ),
    )
    instructions: str = Field(
        description=(
            "Assistant instruction. Sometimes referred to as the " '"system" prompt.'
        ),
    )
    temperature: float = Field(
        default=1e-6,
        description=(
            "Model temperature. The default is slightly "
            "greater-than zero because it is [unknown how OpenAI "
            "handles zero](https://community.openai.com/t/clarifications-on-setting-temperature-0/886447/5)."
        ),
    )


class CallbackRequest(BaseModel):
    callback_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL to call to report endpoint status",
    )


class CreationRequest(
    DocumentOptions,
    AssistantOptions,
    CallbackRequest,
):
    def extract_super_type(self, cls: "CreationRequest"):
        for field_name in cls.__fields__.keys():
            field_value = getattr(self, field_name)
            yield (field_name, field_value)


class DeletionRequest(CallbackRequest):
    collection_id: UUID = Field("Collection to delete")
