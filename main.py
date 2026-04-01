"""Oplit Production Scheduling Service — application entry point."""

import uvicorn
from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(
    title="Oplit Production Scheduler",
    description="Ingests production orders, optimizes machine allocation, and exposes schedule results.",
    version="0.1.0",
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
