from pydantic import BaseModel


class LoginPayload(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    password: str
