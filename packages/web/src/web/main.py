from fastapi import FastAPI

from web.routes import routers

app = FastAPI()
for router in routers:
    app.include_router(router)
