from .admin import router as admin_router
from .login import router as login_router
from .register import router as register_router

routers = [login_router, register_router, admin_router]

__all__ = ["routers"]
