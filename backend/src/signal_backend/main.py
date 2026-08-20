from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from signal_backend.db.session import engine
from signal_backend import models  # noqa: F401  (registers tables with SQLModel metadata)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Signal", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
