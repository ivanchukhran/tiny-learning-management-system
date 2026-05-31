from pydantic import BaseModel, EmailStr, Field


class UserCreateDb(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: EmailStr
    password_hash: str


class UserUpdateDb(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    password_hash: str | None = None
