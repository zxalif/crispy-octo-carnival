"""
Metrics endpoints for scraping statistics and monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from core.logger import get_logger
from api.middleware.auth import verify_api_key
from modules.metrics.scraper_metrics import get_metrics_collector

router = APIRouter(tags=["metrics"])
logger = get_logger(__name__)


@router.get("/scraping/summary")
async def get_scraping_summary(
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """
    Get summary statistics for scraping activity.
    
    Args:
        hours: Number of hours to look back (default: 24)
        
    Returns:
        Summary statistics including success rates, error counts, etc.
    """
    try:
        collector = get_metrics_collector()
        summary = collector.get_summary_stats(hours=hours)
        
        return {
            "summary": summary,
            "time_period_hours": hours
        }
    except Exception as e:
        logger.error("Failed to get scraping summary", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scraping summary: {str(e)}"
        )


@router.get("/scraping/platform/{platform}")
async def get_platform_metrics(
    platform: str,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """
    Get metrics for a specific platform.
    
    Args:
        platform: Platform name (e.g., "reddit")
        hours: Number of hours to look back (default: 24)
        
    Returns:
        Platform-specific metrics
    """
    try:
        collector = get_metrics_collector()
        summary = collector.get_platform_summary(platform=platform, hours=hours)
        
        return summary
    except Exception as e:
        logger.error("Failed to get platform metrics", platform=platform, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get platform metrics: {str(e)}"
        )


@router.get("/scraping/search/{search_id}")
async def get_search_metrics(
    search_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get metrics for a specific keyword search.
    
    Args:
        search_id: Keyword search ID
        
    Returns:
        List of metrics for this search
    """
    try:
        collector = get_metrics_collector()
        metrics = collector.get_search_metrics(search_id)
        
        return {
            "search_id": search_id,
            "metrics": [m.to_dict() for m in metrics],
            "count": len(metrics)
        }
    except Exception as e:
        logger.error("Failed to get search metrics", search_id=search_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get search metrics: {str(e)}"
        )

