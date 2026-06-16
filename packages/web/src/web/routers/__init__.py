from .auth import router as auth_router
from .pages import router as pages_router
from .users import router as users_router

routers = [
    pages_router,
    users_router,
    auth_router,
]

__all__ = ["routers"]
