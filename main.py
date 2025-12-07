from backend.config import get_settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

# Import routers
from routers import (
    auth,
    profiles,
    posts,
    media,
    likes,
    notifications,
    ai,
    admin
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("🚀 Starting FastAPI application...")
    
    # Initialize AI model at startup
    from services.ai_service import get_ai_service
    logger.info("📦 Loading AI detection model...")
    get_ai_service()
    logger.info("✅ AI model loaded successfully")
    
    yield
    
    logger.info("👋 Shutting down application...")

# Create FastAPI app
app = FastAPI(
    title="Social Media API",
    description="API for social media platform with AI content detection",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url, "http://localhost:3000"],  # Trong production, chỉ định domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Include routers
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(posts.router)
app.include_router(media.router)
app.include_router(likes.router)
app.include_router(notifications.router)
app.include_router(ai.router)
app.include_router(admin.router)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Social Media API is running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )