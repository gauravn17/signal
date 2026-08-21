from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from signal_backend.api import candidates, job_descriptions, jobs
from signal_backend.db.session import engine
from signal_backend import models  # noqa: F401  (registers tables with SQLModel metadata)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Signal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(job_descriptions.router)
app.include_router(candidates.router)
app.include_router(jobs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
