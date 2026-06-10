from typing import Annotated

from core.security import hash_password
from database.repositories import create_user
from database.schemas import UserCreateDb
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from web.dependencies import get_session
from web.templates import templates

router = APIRouter()


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),
):
    dto = UserCreateDb(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hash_password(password),
    )
    try:
        user = await create_user(session, dto)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return templates.TemplateResponse(
            request,
            "partials/register_result.html",
            {"ok": False, "error": "Email already registered"},
            status_code=status.HTTP_409_CONFLICT,
        )
    return templates.TemplateResponse(
        request,
        "partials/register_result.html",
        {"ok": True, "email": user.email},
        status_code=status.HTTP_201_CREATED,
    )
