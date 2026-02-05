"""
FastAPI main application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import volume, cycle_time, productivity, suppliers, accuracy

app = FastAPI(
    title="AI Intake Metrics Dashboard API",
    description="API for AI intake metrics dashboard with volume, cycle time, and productivity metrics",
    version="1.0.0",
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and CRA defaults
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(volume.router, prefix="/api/volume", tags=["Volume Metrics"])
app.include_router(cycle_time.router, prefix="/api/cycle-time", tags=["Cycle Time Metrics"])
app.include_router(productivity.router, prefix="/api/productivity", tags=["Productivity Metrics"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])
app.include_router(accuracy.router, prefix="/api/accuracy", tags=["Accuracy Metrics"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AI Intake Metrics Dashboard API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies backend and database connectivity.
    """
    from app.database import execute_query
    
    try:
        # Quick database connectivity check
        execute_query("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/version")
async def version_info():
    """
    Return current application version.
    """
    try:
        with open("../VERSION", "r") as f:
            version = f.read().strip()
        return {
            "version": version,
            "environment": "local"
        }
    except Exception:
        return {
            "version": "unknown",
            "environment": "local"
        }
