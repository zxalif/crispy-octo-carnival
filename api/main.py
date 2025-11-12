"""
FastAPI application for Rixly.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_config
from core.logger import get_logger, setup_logging
from modules.scheduler.scheduler import RixlyScheduler
from modules.database.storage import LeadStorage
from api.routes import keyword_searches, leads, utilities, metrics
from api.middleware.error_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    api_error_handler,
    APIError
)
from api.middleware.rate_limit import limiter, rate_limit_handler
from slowapi.errors import RateLimitExceeded

logger = get_logger(__name__)
config = get_config()

# Global scheduler instance
_scheduler: RixlyScheduler = None


def get_scheduler() -> RixlyScheduler:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = RixlyScheduler()
    return _scheduler


# Create FastAPI app
app = FastAPI(
    title="Rixly API",
    description="Reddit lead generation API (simplified, no agent)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS middleware
# In production, restrict to specific origins
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Use CORS_ORIGINS env var or allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(APIError, api_error_handler)

# Include routers
app.include_router(keyword_searches.router, prefix="/api/v1/keyword-searches", tags=["keyword-searches"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["leads"])
app.include_router(utilities.router, prefix="/api/v1", tags=["utilities"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Rixly API",
        "version": "1.0.0",
        "description": "Reddit lead generation API",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint with detailed status.
    
    Returns:
        Health status including database connectivity and external services
    """
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "services": {}
    }
    
    # Check database
    try:
        storage = LeadStorage()
        # Try to query database
        storage.list_keyword_searches(limit=1)
        health_status["services"]["database"] = {
            "status": "healthy",
            "type": "postgresql"
        }
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        health_status["status"] = "degraded"
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check scheduler
    try:
        scheduler = get_scheduler()
        health_status["services"]["scheduler"] = {
            "status": "healthy" if scheduler.is_running() else "stopped",
            "running": scheduler.is_running()
        }
    except Exception as e:
        logger.error("Scheduler health check failed", error=str(e))
        health_status["services"]["scheduler"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check configuration
    health_status["services"]["config"] = {
        "status": "healthy",
        "scheduler_enabled": config.scheduler_enabled,
        "environment": config.environment
    }
    
    # Check VPN status (if enabled)
    try:
        from modules.vpn import get_vpn_status
        vpn_status = get_vpn_status()
        health_status["services"]["vpn"] = vpn_status
    except Exception as e:
        logger.debug("VPN status check failed", error=str(e))
        health_status["services"]["vpn"] = {
            "status": "not_configured",
            "message": "VPN not available"
        }
    
    # Check Reddit API connectivity (optional - only if credentials are configured)
    # This is a lightweight check that doesn't affect overall health status
    try:
        from modules.reddit.scraper import RedditScraper
        
        # Only check if Reddit credentials are configured
        if config.reddit_client_id and config.reddit_client_secret:
            scraper = None
            try:
                scraper = RedditScraper()
                # Try to access Reddit API (simple connectivity test with timeout)
                reddit = scraper.reddit
                test_subreddit = await reddit.subreddit("test")
                # Just accessing it is enough to test connectivity
                await test_subreddit.load()
                
                health_status["services"]["reddit_api"] = {
                    "status": "healthy",
                    "connected": True
                }
            except Exception as reddit_error:
                # Don't degrade overall health for Reddit API issues
                # Reddit API is external and may have transient issues
                health_status["services"]["reddit_api"] = {
                    "status": "unhealthy",
                    "connected": False,
                    "error": str(reddit_error)[:100]  # Truncate long error messages
                }
                # Only log at debug level to avoid noise in logs
                logger.debug("Reddit API connectivity check failed", error=str(reddit_error))
            finally:
                # Clean up Reddit client to prevent unclosed session warnings
                if scraper:
                    try:
                        await scraper.close()
                    except Exception as cleanup_error:
                        logger.debug("Error closing Reddit client in health check", error=str(cleanup_error))
        else:
            # Reddit credentials not configured - skip check
            health_status["services"]["reddit_api"] = {
                "status": "not_configured",
                "message": "Reddit credentials not configured"
            }
    except Exception as e:
        # Don't fail health check if Reddit check itself fails
        logger.debug("Reddit API health check failed", error=str(e))
        health_status["services"]["reddit_api"] = {
            "status": "error",
            "error": str(e)[:100]
        }
    
    # Determine overall status
    if health_status["status"] == "healthy":
        # Check if any service is unhealthy
        for service, status_info in health_status["services"].items():
            if isinstance(status_info, dict) and status_info.get("status") == "unhealthy":
                health_status["status"] = "degraded"
                break
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.on_event("startup")
async def startup_event():
    """Startup event."""
    # Setup logging (writes to both console and file)
    setup_logging(log_level=config.log_level, log_file=config.log_file)
    
    logger.info("Starting Rixly API")
    
    # Start scheduler if enabled
    if config.scheduler_enabled:
        scheduler = get_scheduler()
        scheduler.start()
        logger.info("Scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info("Shutting down Rixly API")
    
    # Stop scheduler
    global _scheduler
    if _scheduler and _scheduler.is_running():
        _scheduler.stop()
        logger.info("Scheduler stopped")

