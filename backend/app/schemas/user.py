from pydantic import BaseModel,ConfigDict

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class UserResponse(BaseModel):
    id:int
    username:str
    name:str
    role:str
    email:str | None=None
    phone:str | None=None
    avatar:str | None =None
    status:int

    model_config=ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    name: str| None =None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None 
    role:str | None=None
    status:int | None=None


class PasswordUpdateRequest(BaseModel):
    """修改密码的请求参数"""
    old_password:str
    new_password:str


class UserCreateRequest(BaseModel):
    name: str| None =None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None 
    role: Literal["student", "admin"] = "student"
    status: Literal[0, 1] = 1
    username: str = Field(min_length=1, max_length=50)
    password:str="123"
    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value
