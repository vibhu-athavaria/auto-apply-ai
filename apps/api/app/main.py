from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.cost_logging_middleware import CostLoggingMiddleware
from app.routers import auth, resumes, profiles, health, jobs, tailor
from app.utils.logger import setup_logging

# Setup structured logging
setup_logging()

app = FastAPI(title="LinkedIn Autopilot API", version="1.0.0")

# Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(CostLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(tailor.router, prefix="/jobs", tags=["tailor"])
app.include_router(health.router, prefix="/health", tags=["health"])

@app.on_event("startup")
async def startup_event():
    await create_tables()