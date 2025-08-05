from sqlmodel import SQLModel, Field


class Pagination(SQLModel):
    """
    Pagination metadata for API responses.
    """
    total: int = Field(..., description="Total number of items", ge=0)
    skip: int = Field(..., description="Number of items to skip", ge=0)
    limit: int = Field(..., description="Maximum number of items to return", ge=1, le=100)

    @classmethod
    def build(cls, total: int, skip: int, limit: int) -> dict:
        return {"pagination": cls(total=total, skip=skip, limit=limit).model_dump()}
