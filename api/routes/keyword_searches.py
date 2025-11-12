"""
Keyword search management endpoints.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.logger import get_logger
from core.processor import process_keyword_search
from core.state import KeywordSearchState
from modules.database.storage import LeadStorage
from modules.keywords.manager import KeywordSearchManager
from modules.jobs.tracker import get_job_tracker
from api.middleware.auth import verify_api_key
from api.middleware.rate_limit import limiter
from api.models.schemas import (
    KeywordSearchCreate,
    KeywordSearchUpdate,
    KeywordSearchResponse,
    ScrapeResponse
)

router = APIRouter(tags=["keyword-searches"])
logger = get_logger(__name__)


def get_storage() -> LeadStorage:
    """Get storage instance."""
    return LeadStorage()


def get_manager() -> KeywordSearchManager:
    """Get keyword search manager."""
    storage = get_storage()
    return KeywordSearchManager(storage)


@router.post("", response_model=KeywordSearchResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def create_keyword_search(
    request: Request,
    search: KeywordSearchCreate,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager)
):
    """Create a new keyword search."""
    try:
        # Build reddit_config if not provided
        reddit_config = search.reddit_config
        if not reddit_config and "reddit" in search.platforms:
            # Default Reddit config
            reddit_config = {
                "subreddits": [],
                "limit": 100,
                "include_comments": True,
                "sort": "new",
                "time_filter": "day"
            }
        
        # Validate reddit_config if Reddit is in platforms
        if "reddit" in search.platforms:
            if not reddit_config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="reddit_config is required when 'reddit' is in platforms"
                )
            
            # Ensure subreddits array exists (but allow empty for global search)
            subreddits = reddit_config.get("subreddits", [])
            if not isinstance(subreddits, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="reddit_config.subreddits must be an array. Use empty array [] to search all of Reddit, or provide specific subreddits like [\"forhire\", \"freelance\"]"
                )
            
            # If subreddits is empty, we'll search all of Reddit (using r/all)
            # This is valid and supported
        
        search_state = manager.create_search(
            name=search.name,
            keywords=search.keywords,
            patterns=search.patterns,
            platforms=search.platforms,
            reddit_config=reddit_config,
            scraping_mode=search.scraping_mode,
            scraping_interval=search.scraping_interval,
            enabled=search.enabled,
            webhook_url=search.webhook_url
        )
        
        # Convert to response
        storage = get_storage()
        search_model = storage.get_keyword_search(search_state.id)
        
        return KeywordSearchResponse.model_validate(search_model)
        
    except Exception as e:
        logger.error("Failed to create keyword search", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create keyword search: {str(e)}"
        )


@router.get("", response_model=List[KeywordSearchResponse])
async def list_keyword_searches(
    enabled: bool = None,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager)
):
    """List keyword searches."""
    try:
        searches = manager.list_searches(enabled_only=enabled if enabled is not None else False)
        
        # Apply pagination
        paginated = searches[offset:offset + limit]
        
        # Convert to response models
        storage = get_storage()
        response_models = []
        for search_state in paginated:
            search_model = storage.get_keyword_search(search_state.id)
            if search_model:
                response_models.append(KeywordSearchResponse.model_validate(search_model))
        
        return response_models
        
    except Exception as e:
        logger.error("Failed to list keyword searches", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list keyword searches: {str(e)}"
        )


@router.get("/{search_id}", response_model=KeywordSearchResponse)
async def get_keyword_search(
    search_id: str,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager)
):
    """Get a keyword search by ID."""
    search = manager.get_search(search_id)
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )
    
    storage = get_storage()
    search_model = storage.get_keyword_search(search_id)
    return KeywordSearchResponse.model_validate(search_model)


@router.put("/{search_id}", response_model=KeywordSearchResponse)
async def update_keyword_search(
    search_id: str,
    update: KeywordSearchUpdate,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager),
    storage: LeadStorage = Depends(get_storage)
):
    """Update a keyword search."""
    # Get existing search to validate against current state
    existing_search = manager.get_search(search_id)
    if not existing_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )
    
    # Validate reddit_config if Reddit is in platforms
    final_platforms = update.platforms if update.platforms is not None else existing_search.platforms
    final_reddit_config = update.reddit_config if update.reddit_config is not None else existing_search.reddit_config
    
    if "reddit" in final_platforms:
        if not final_reddit_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reddit_config is required when 'reddit' is in platforms"
            )
        
        # Ensure subreddits array exists (but allow empty for global search)
        subreddits = final_reddit_config.get("subreddits", [])
        if not isinstance(subreddits, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reddit_config.subreddits must be an array. Use empty array [] to search all of Reddit, or provide specific subreddits like [\"forhire\", \"freelance\"]"
            )
        
        # If subreddits is empty, we'll search all of Reddit (using r/all)
        # This is valid and supported
    
    # Validate scraping mode/interval combination
    # Determine what the final mode and interval will be
    final_mode = update.scraping_mode if update.scraping_mode is not None else existing_search.scraping_mode
    final_interval = update.scraping_interval if update.scraping_interval is not None else existing_search.scraping_interval
    
    # Validate combination
    if final_mode == 'scheduled' and not final_interval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scraping_interval is required when scraping_mode is 'scheduled'. Provide one of: '30m', '1h', '6h', '24h'"
        )
    elif final_mode == 'one_time' and final_interval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scraping_interval should not be provided when scraping_mode is 'one_time'. One-time searches don't use intervals."
        )
    
    # Build update dict (only include non-None values)
    updates = {}
    if update.name is not None:
        updates["name"] = update.name
    if update.keywords is not None:
        updates["keywords"] = update.keywords
    if update.patterns is not None:
        updates["patterns"] = update.patterns
    if update.platforms is not None:
        updates["platforms"] = update.platforms
    if update.reddit_config is not None:
        updates["reddit_config"] = update.reddit_config
    if update.scraping_mode is not None:
        updates["scraping_mode"] = update.scraping_mode
    if update.scraping_interval is not None:
        updates["scraping_interval"] = update.scraping_interval
    elif update.scraping_mode == 'one_time':
        # If changing to one_time, clear the interval
        updates["scraping_interval"] = None
    if update.enabled is not None:
        updates["enabled"] = update.enabled
    if update.webhook_url is not None:
        updates["webhook_url"] = update.webhook_url
    
    updated_search = manager.update_search(search_id, **updates)
    if not updated_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )
    
    storage = get_storage()
    search_model = storage.get_keyword_search(search_id)
    return KeywordSearchResponse.model_validate(search_model)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword_search(
    search_id: str,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager)
):
    """Delete a keyword search."""
    deleted = manager.delete_search(search_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )


@router.post("/{search_id}/scrape", response_model=ScrapeResponse)
@limiter.limit("5/minute")  # Rate limit: 5 scrapes per minute
async def trigger_scrape(
    request: Request,
    search_id: str,
    api_key: str = Depends(verify_api_key),
    manager: KeywordSearchManager = Depends(get_manager),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Trigger a one-time scrape for a keyword search.
    
    This endpoint:
    - Checks if a job is already running (prevents conflicts)
    - Enforces cooldown period (minimum 5 minutes between scrapes)
    - Tracks job status in database and memory
    - Returns error if job is already running or cooldown not met
    """
    search = manager.get_search(search_id)
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )
    
    if not search.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Keyword search {search_id} is disabled"
        )
    
    # Check job tracker for conflicts
    job_tracker = get_job_tracker(storage)
    can_start, reason = job_tracker.can_start_job(search_id)
    
    if not can_start:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=reason or f"Job already running for search {search_id}"
        )
    
    # Start job tracking
    if not job_tracker.start_job(search_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to start job for search {search_id}"
        )
    
    # Update database with job status
    try:
        search_model = storage.get_keyword_search(search_id)
        if search_model:
            search_state = KeywordSearchState(
                id=search_model.id,
                name=search_model.name,
                keywords=search_model.keywords,
                patterns=search_model.patterns,
                platforms=search_model.platforms,
                reddit_config=search_model.reddit_config,
                linkedin_config=search_model.linkedin_config,
                twitter_config=search_model.twitter_config,
                scraping_mode=search_model.scraping_mode,
                scraping_interval=search_model.scraping_interval,
                enabled=search_model.enabled,
                created_at=search_model.created_at,
                updated_at=datetime.utcnow(),
                last_scrape_at=search_model.last_scrape_at,
                next_scrape_at=search_model.next_scrape_at,
                scraping_status="running",
                scraping_started_at=datetime.utcnow(),
                scraping_completed_at=None,
                scraping_error=None
            )
            storage.save_keyword_search(search_state)
    except Exception as e:
        logger.warning("Failed to update job status in database", search_id=search_id, error=str(e))
    
    try:
        # Process the keyword search
        result = await process_keyword_search(search, storage)
        
        # Mark as scraped and completed
        manager.mark_scraped(search_id)
        job_tracker.complete_job(search_id, success=True)
        
        # Update database with completion
        try:
            search_model = storage.get_keyword_search(search_id)
            if search_model:
                search_state = KeywordSearchState(
                    id=search_model.id,
                    name=search_model.name,
                    keywords=search_model.keywords,
                    patterns=search_model.patterns,
                    platforms=search_model.platforms,
                    reddit_config=search_model.reddit_config,
                    linkedin_config=search_model.linkedin_config,
                    twitter_config=search_model.twitter_config,
                    scraping_mode=search_model.scraping_mode,
                    scraping_interval=search_model.scraping_interval,
                    enabled=search_model.enabled,
                    created_at=search_model.created_at,
                    updated_at=datetime.utcnow(),
                    last_scrape_at=search_model.last_scrape_at,
                    next_scrape_at=search_model.next_scrape_at,
                    scraping_status="completed",
                    scraping_started_at=search_model.scraping_started_at,
                    scraping_completed_at=datetime.utcnow(),
                    scraping_error=None
                )
                storage.save_keyword_search(search_state)
        except Exception as e:
            logger.warning("Failed to update completion status in database", search_id=search_id, error=str(e))
        
        return ScrapeResponse(**result)
        
    except Exception as e:
        # Mark job as failed
        error_msg = str(e)
        job_tracker.complete_job(search_id, success=False, error=error_msg)
        
        # Update database with failure
        try:
            search_model = storage.get_keyword_search(search_id)
            if search_model:
                search_state = KeywordSearchState(
                    id=search_model.id,
                    name=search_model.name,
                    keywords=search_model.keywords,
                    patterns=search_model.patterns,
                    platforms=search_model.platforms,
                    reddit_config=search_model.reddit_config,
                    linkedin_config=search_model.linkedin_config,
                    twitter_config=search_model.twitter_config,
                    scraping_mode=search_model.scraping_mode,
                    scraping_interval=search_model.scraping_interval,
                    enabled=search_model.enabled,
                    created_at=search_model.created_at,
                    updated_at=datetime.utcnow(),
                    last_scrape_at=search_model.last_scrape_at,
                    next_scrape_at=search_model.next_scrape_at,
                    scraping_status="failed",
                    scraping_started_at=search_model.scraping_started_at,
                    scraping_completed_at=datetime.utcnow(),
                    scraping_error=error_msg
                )
                storage.save_keyword_search(search_state)
        except Exception as db_error:
            logger.warning("Failed to update failure status in database", search_id=search_id, error=str(db_error))
        
        logger.error("Failed to scrape keyword search", search_id=search_id, error=error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scrape: {error_msg}"
        )


@router.get("/{search_id}/status")
async def get_search_status(
    search_id: str,
    api_key: str = Depends(verify_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Get current scraping status for a keyword search.
    
    Returns job status including:
    - Whether a job is currently running
    - Time since last scrape
    - Cooldown information
    - Job history
    """
    search_model = storage.get_keyword_search(search_id)
    if not search_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword search {search_id} not found"
        )
    
    job_tracker = get_job_tracker(storage)
    job_status = job_tracker.get_job_status(search_id)
    
    # Calculate time since last scrape
    time_since_last = None
    if search_model.last_scrape_at:
        time_since_last = (datetime.utcnow() - search_model.last_scrape_at).total_seconds() / 60  # minutes
    
    # Check if can start (cooldown info)
    can_start, reason = job_tracker.can_start_job(search_id)
    
    return {
        "search_id": search_id,
        "scraping_status": search_model.scraping_status,
        "is_running": job_tracker.is_job_running(search_id),
        "can_start": can_start,
        "reason_if_not": reason,
        "last_scrape_at": search_model.last_scrape_at.isoformat() if search_model.last_scrape_at else None,
        "time_since_last_minutes": round(time_since_last, 2) if time_since_last else None,
        "scraping_started_at": search_model.scraping_started_at.isoformat() if search_model.scraping_started_at else None,
        "scraping_completed_at": search_model.scraping_completed_at.isoformat() if search_model.scraping_completed_at else None,
        "scraping_error": search_model.scraping_error,
        "job_info": job_status
    }
