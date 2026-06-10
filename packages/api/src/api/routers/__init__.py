from .auth import router as auth_router
from .user import router as user_router

routers = [
    auth_router,
    user_router,
]

__all__ = ["routers"]
