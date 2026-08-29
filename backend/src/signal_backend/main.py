from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from signal_backend.api import candidates, job_descriptions, jobs, stats
from signal_backend import models  # noqa: F401  (registers tables with SQLModel metadata)

app = FastAPI(title="Signal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(job_descriptions.router)
app.include_router(candidates.router)
app.include_router(jobs.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
