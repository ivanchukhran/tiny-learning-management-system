from pydantic import BaseModel, EmailStr, Field

from database.constants import FIRST_NAME_MAX_LENGTH, LAST_NAME_MAX_LENGTH


class UserCreateDb(BaseModel):
    first_name: str = Field(max_length=FIRST_NAME_MAX_LENGTH)
    last_name: str = Field(max_length=LAST_NAME_MAX_LENGTH)
    email: EmailStr
    password_hash: str


class UserUpdateDb(BaseModel):
    first_name: str | None = Field(default=None, max_length=FIRST_NAME_MAX_LENGTH)
    last_name: str | None = Field(default=None, max_length=LAST_NAME_MAX_LENGTH)
    email: EmailStr | None = None
    password_hash: str | None = None
