from datetime import datetime

from database.constants import FIRST_NAME_MAX_LENGTH, LAST_NAME_MAX_LENGTH
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.constants import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH


class UserBase(BaseModel):
    first_name: str = Field(max_length=FIRST_NAME_MAX_LENGTH)
    last_name: str = Field(max_length=LAST_NAME_MAX_LENGTH)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class UserUpdate(BaseModel):
    # Partial update: every field optional. model_dump(exclude_unset=True) at the
    # call site yields only the fields the client actually sent, so untouched
    # columns are preserved. Password is not here - it has its own
    # PUT /users/{id}/password endpoint.
    first_name: str | None = Field(default=None, max_length=FIRST_NAME_MAX_LENGTH)
    last_name: str | None = Field(default=None, max_length=LAST_NAME_MAX_LENGTH)
    email: EmailStr | None = None


class PasswordUpdate(BaseModel):
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
