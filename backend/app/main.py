import logging
from fastapi import FastAPI # type: ignore
from app.routes.search import router

app = FastAPI()

app.include_router(router)
logging.getLogger("neo4j").setLevel(logging.ERROR)
