from typing import Annotated

from core.constants import SESSION_COOKIE_NAME, SESSION_MAX_LIFETIME
from core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)
from database.models import User
from database.repositories import create_session, get_user
from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from web.dependencies import get_session
from web.templates import templates

router = APIRouter()

_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_MAX_LIFETIME.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),
):
    user = await get_user(session, User.email == email)
    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    valid = verify_password(password, password_hash)
    if user is None or not valid:
        return templates.TemplateResponse(
            request,
            "partials/login_result.html",
            {"ok": False, "error": "Invalid credentials"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = generate_session_token()
    await create_session(session, user.id, hash_token(token))
    await session.commit()

    response = templates.TemplateResponse(
        request,
        "partials/login_result.html",
        {"ok": True, "email": user.email},
    )
    _set_session_cookie(response, token)
    return response
