
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=12, max_length=128)
    role: str = "CUSTOMER"


class AdminUpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)


class ChangeUserRoleRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class UserAdminResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)
