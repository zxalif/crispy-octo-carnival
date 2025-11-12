"""
Lead management endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.logger import get_logger
from modules.database.storage import LeadStorage
from api.middleware.auth import verify_api_key
from api.models.schemas import LeadResponse, LeadUpdate, StatisticsResponse, PaginatedLeadsResponse

router = APIRouter(tags=["leads"])
logger = get_logger(__name__)


def get_storage() -> LeadStorage:
    """Get storage instance."""
    return LeadStorage()


@router.get("", response_model=PaginatedLeadsResponse)
async def list_leads(
    keyword_search_id: Optional[str] = Query(None, description="Filter by keyword search ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    opportunity_type: Optional[str] = Query(None, description="Filter by opportunity type"),
    min_score: Optional[float] = Query(None, description="Minimum score threshold"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    api_key: str = Depends(verify_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """
    List leads with filters and pagination metadata.
    
    Returns paginated response with:
    - items: List of leads
    - total: Total number of leads matching filters
    - limit: Items per page
    - offset: Current offset
    - has_more: Whether there are more items
    """
    try:
        leads, total = storage.list_leads(
            keyword_search_id=keyword_search_id,
            status=status,
            opportunity_type=opportunity_type,
            min_score=min_score,
            limit=limit,
            offset=offset
        )
        
        return PaginatedLeadsResponse(
            items=[LeadResponse.model_validate(lead) for lead in leads],
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(leads)) < total
        )
        
    except Exception as e:
        logger.error("Failed to list leads", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list leads: {str(e)}"
        )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    api_key: str = Depends(verify_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """Get a lead by ID."""
    lead = storage.get_lead(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    update: LeadUpdate,
    api_key: str = Depends(verify_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """Update a lead (currently only status)."""
    if update.status:
        updated_lead = storage.update_lead_status(lead_id, update.status)
        if not updated_lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead {lead_id} not found"
            )
        return LeadResponse.model_validate(updated_lead)
    else:
        # No updates provided
        lead = storage.get_lead(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead {lead_id} not found"
            )
        return LeadResponse.model_validate(lead)


@router.get("/statistics/summary", response_model=StatisticsResponse)
async def get_statistics(
    keyword_search_id: Optional[str] = Query(None, description="Filter by keyword search ID"),
    api_key: str = Depends(verify_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """Get lead statistics."""
    try:
        stats = storage.get_statistics(keyword_search_id=keyword_search_id)
        return StatisticsResponse(**stats)
        
    except Exception as e:
        logger.error("Failed to get statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )

