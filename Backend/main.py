"""
Entry point for the esports backend server.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from valorant.routes import router as valorant_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="Esports Stats API",
    description="Backend for CSU esports stats — Valorant (and future games).",
    version="0.1.0",
)

# Allow the Next.js dev server and any future frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(valorant_router, prefix="/api/valorant")


@app.get("/")
def root():
    return {"status": "ok", "message": "Esports Stats API is running."}


@app.get("/health")
def health():
    return {"status": "healthy"}
