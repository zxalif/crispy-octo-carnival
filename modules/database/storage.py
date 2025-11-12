"""
Database storage operations for Rixly.
Simplified - no LeadHistory, no integrations.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, desc, and_, or_
from sqlalchemy.orm import sessionmaker, Session

from core.config import get_config
from core.logger import get_logger
from core.state import KeywordSearchState, LeadState
from modules.database.models import Base, KeywordSearch, Lead, ScrapedContent, LLMCache

logger = get_logger(__name__)


class LeadStorage:
    """Handles database operations for leads and keyword searches."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize storage.
        
        Args:
            database_url: Database URL (uses config if not provided)
        """
        config = get_config()
        
        # Determine database URL
        if database_url:
            self.database_url = database_url
        elif config.database_url:
            self.database_url = config.database_url
        else:
            # Use parts to build URL (defaults to PostgreSQL)
            self.database_url = config.database_url_from_parts
        
        # Create engine
        self.engine = create_engine(self.database_url, echo=False)
        
        # Note: Tables are created via Alembic migrations, not here
        # Base.metadata.create_all(self.engine)  # Removed - use Alembic instead
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        logger.info("Initialized LeadStorage", database_url=self.database_url)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    # Keyword Search Operations
    
    def save_keyword_search(self, search_state: KeywordSearchState) -> KeywordSearch:
        """
        Save or update a keyword search.
        
        Args:
            search_state: Keyword search state
            
        Returns:
            Saved KeywordSearch model
        """
        session = self.get_session()
        try:
            # Check if exists
            existing = session.query(KeywordSearch).filter_by(id=search_state.id).first()
            
            if existing:
                # Update
                existing.name = search_state.name
                existing.keywords = search_state.keywords
                existing.patterns = search_state.patterns
                existing.platforms = search_state.platforms
                existing.reddit_config = search_state.reddit_config
                existing.linkedin_config = search_state.linkedin_config
                existing.twitter_config = search_state.twitter_config
                existing.scraping_mode = search_state.scraping_mode
                existing.scraping_interval = search_state.scraping_interval
                existing.enabled = search_state.enabled
                existing.last_scrape_at = search_state.last_scrape_at
                existing.next_scrape_at = search_state.next_scrape_at
                existing.scraping_status = getattr(search_state, "scraping_status", None)
                existing.scraping_started_at = getattr(search_state, "scraping_started_at", None)
                existing.scraping_completed_at = getattr(search_state, "scraping_completed_at", None)
                existing.scraping_error = getattr(search_state, "scraping_error", None)
                existing.webhook_url = getattr(search_state, "webhook_url", None)
                existing.updated_at = search_state.updated_at
                
                logger.info("Updated keyword search", search_id=search_state.id)
            else:
                # Create new
                existing = KeywordSearch(
                    id=search_state.id,
                    name=search_state.name,
                    keywords=search_state.keywords,
                    patterns=search_state.patterns,
                    platforms=search_state.platforms,
                    reddit_config=search_state.reddit_config,
                    linkedin_config=search_state.linkedin_config,
                    twitter_config=search_state.twitter_config,
                    scraping_mode=search_state.scraping_mode,
                    scraping_interval=search_state.scraping_interval,
                    enabled=search_state.enabled,
                    created_at=search_state.created_at,
                    updated_at=search_state.updated_at,
                    last_scrape_at=search_state.last_scrape_at,
                    next_scrape_at=search_state.next_scrape_at,
                    scraping_status=getattr(search_state, "scraping_status", None),
                    scraping_started_at=getattr(search_state, "scraping_started_at", None),
                    scraping_completed_at=getattr(search_state, "scraping_completed_at", None),
                    scraping_error=getattr(search_state, "scraping_error", None),
                    webhook_url=getattr(search_state, "webhook_url", None)
                )
                session.add(existing)
                logger.info("Created keyword search", search_id=search_state.id)
            
            session.commit()
            session.refresh(existing)
            return existing
            
        finally:
            session.close()
    
    def get_keyword_search(self, search_id: str) -> Optional[KeywordSearch]:
        """Get a keyword search by ID."""
        session = self.get_session()
        try:
            return session.query(KeywordSearch).filter_by(id=search_id).first()
        finally:
            session.close()
    
    def list_keyword_searches(
        self,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[KeywordSearch]:
        """List keyword searches."""
        session = self.get_session()
        try:
            query = session.query(KeywordSearch)
            
            if enabled_only:
                query = query.filter_by(enabled=True)
            
            query = query.order_by(desc(KeywordSearch.created_at))
            query = query.limit(limit).offset(offset)
            
            return query.all()
        finally:
            session.close()
    
    def get_due_keyword_searches(self) -> List[KeywordSearch]:
        """
        Get keyword searches that are due for scraping.
        
        Returns:
            List of keyword searches where next_scrape_at <= now
        """
        session = self.get_session()
        try:
            now = datetime.utcnow()
            return session.query(KeywordSearch).filter(
                and_(
                    KeywordSearch.enabled == True,
                    KeywordSearch.scraping_mode == "scheduled",
                    KeywordSearch.next_scrape_at <= now
                )
            ).all()
        finally:
            session.close()
    
    def delete_keyword_search(self, search_id: str) -> bool:
        """Delete a keyword search."""
        session = self.get_session()
        try:
            search = session.query(KeywordSearch).filter_by(id=search_id).first()
            if not search:
                return False
            
            session.delete(search)
            session.commit()
            logger.info("Deleted keyword search", search_id=search_id)
            return True
        finally:
            session.close()
    
    # Lead Operations
    
    def save_lead(self, lead_state: LeadState) -> Optional[Lead]:
        """
        Save a lead (with duplicate detection).
        
        Args:
            lead_state: Lead state
            
        Returns:
            Saved Lead model or None if duplicate
        """
        session = self.get_session()
        try:
            # Check for duplicate by source_id + keyword_search_id
            existing = session.query(Lead).filter(
                and_(
                    Lead.source_id == lead_state.source_id,
                    Lead.keyword_search_id == lead_state.keyword_search_id
                )
            ).first()
            
            if existing:
                logger.debug("Lead already exists", lead_id=existing.id, source_id=lead_state.source_id)
                return existing
            
            # Create new lead
            lead = Lead(
                id=lead_state.id,
                keyword_search_id=lead_state.keyword_search_id,
                source=lead_state.source,
                source_type=lead_state.source_type,
                source_id=lead_state.source_id,
                parent_post_id=lead_state.parent_post_id,
                title=lead_state.title,
                content=lead_state.content,
                author=lead_state.author,
                url=lead_state.url,
                matched_keywords=lead_state.matched_keywords,
                detected_pattern=lead_state.detected_pattern,
                domain=lead_state.domain,
                company=lead_state.company,
                email=lead_state.email,
                author_profile_url=lead_state.author_profile_url,
                social_profiles=lead_state.social_profiles,
                opportunity_type=lead_state.opportunity_type,
                opportunity_subtype=lead_state.opportunity_subtype,
                relevance_score=lead_state.relevance_score,
                urgency_score=lead_state.urgency_score,
                total_score=lead_state.total_score,
                extracted_info=lead_state.extracted_info,
                status=lead_state.status,
                created_at=lead_state.created_at,
                updated_at=lead_state.updated_at
            )
            
            session.add(lead)
            session.commit()
            session.refresh(lead)
            
            logger.info("Saved lead", lead_id=lead.id, type=lead.opportunity_type, score=lead.total_score)
            
            return lead
            
        finally:
            session.close()
    
    def save_leads_batch(self, lead_states: List[LeadState]) -> List[Lead]:
        """Save multiple leads in batch."""
        saved_leads = []
        for lead_state in lead_states:
            lead = self.save_lead(lead_state)
            if lead:
                saved_leads.append(lead)
        
        logger.info("Saved leads batch", total=len(lead_states), saved=len(saved_leads))
        
        return saved_leads
    
    def get_lead(self, lead_id: str) -> Optional[Lead]:
        """Get a lead by ID."""
        session = self.get_session()
        try:
            return session.query(Lead).filter_by(id=lead_id).first()
        finally:
            session.close()
    
    def get_lead_by_source_id(
        self,
        source_id: str,
        keyword_search_id: str
    ) -> Optional[Lead]:
        """Get a lead by source_id and keyword_search_id."""
        session = self.get_session()
        try:
            return session.query(Lead).filter(
                and_(
                    Lead.source_id == source_id,
                    Lead.keyword_search_id == keyword_search_id
                )
            ).first()
        finally:
            session.close()
    
    def list_leads(
        self,
        keyword_search_id: Optional[str] = None,
        status: Optional[str] = None,
        opportunity_type: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Lead], int]:
        """
        List leads with filters and return total count.
        
        Returns:
            Tuple of (leads list, total count)
        """
        session = self.get_session()
        try:
            # Base query for filtering
            query = session.query(Lead)
            count_query = session.query(Lead)
            
            if keyword_search_id:
                query = query.filter_by(keyword_search_id=keyword_search_id)
                count_query = count_query.filter_by(keyword_search_id=keyword_search_id)
            
            if status:
                query = query.filter_by(status=status)
                count_query = count_query.filter_by(status=status)
            
            if opportunity_type:
                query = query.filter_by(opportunity_type=opportunity_type)
                count_query = count_query.filter_by(opportunity_type=opportunity_type)
            
            if min_score is not None:
                query = query.filter(Lead.total_score >= min_score)
                count_query = count_query.filter(Lead.total_score >= min_score)
            
            # Get total count
            total_count = count_query.count()
            
            # Apply ordering and pagination
            query = query.order_by(desc(Lead.total_score), desc(Lead.created_at))
            query = query.limit(limit).offset(offset)
            
            leads = query.all()
            return leads, total_count
        finally:
            session.close()
    
    def count_leads(
        self,
        keyword_search_id: Optional[str] = None,
        status: Optional[str] = None,
        opportunity_type: Optional[str] = None,
        min_score: Optional[float] = None
    ) -> int:
        """Count leads matching filters."""
        session = self.get_session()
        try:
            query = session.query(Lead)
            
            if keyword_search_id:
                query = query.filter_by(keyword_search_id=keyword_search_id)
            
            if status:
                query = query.filter_by(status=status)
            
            if opportunity_type:
                query = query.filter_by(opportunity_type=opportunity_type)
            
            if min_score is not None:
                query = query.filter(Lead.total_score >= min_score)
            
            return query.count()
        finally:
            session.close()
    
    def update_lead_status(
        self,
        lead_id: str,
        new_status: str,
        notes: Optional[str] = None
    ) -> Optional[Lead]:
        """Update lead status."""
        session = self.get_session()
        try:
            lead = session.query(Lead).filter_by(id=lead_id).first()
            if not lead:
                return None
            
            lead.status = new_status
            lead.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(lead)
            
            logger.info("Updated lead status", lead_id=lead_id, new=new_status)
            
            return lead
            
        finally:
            session.close()
    
    def get_statistics(
        self,
        keyword_search_id: Optional[str] = None
    ) -> Dict[str, any]:
        """Get statistics for leads."""
        session = self.get_session()
        try:
            query = session.query(Lead)
            
            if keyword_search_id:
                query = query.filter_by(keyword_search_id=keyword_search_id)
            
            total = query.count()
            by_status = {}
            by_type = {}
            
            # Count by status
            for status in ["new", "qualified", "contacted", "converted"]:
                count = query.filter_by(status=status).count()
                by_status[status] = count
            
            # Count by opportunity type
            types = session.query(Lead.opportunity_type).distinct().all()
            for (opp_type,) in types:
                if opp_type:
                    count = query.filter_by(opportunity_type=opp_type).count()
                    by_type[opp_type] = count
            
            return {
                "total_leads": total,
                "by_status": by_status,
                "by_opportunity_type": by_type
            }
        finally:
            session.close()
    
    # Scraped Content Operations (for duplicate prevention)
    
    def is_content_scraped(
        self,
        keyword_search_id: str,
        source: str,
        source_id: str
    ) -> bool:
        """
        Check if content has already been scraped.
        
        Args:
            keyword_search_id: Keyword search ID
            source: Source platform (reddit, linkedin, twitter)
            source_id: Source ID (post/comment ID)
            
        Returns:
            True if already scraped, False otherwise
        """
        session = self.get_session()
        try:
            existing = session.query(ScrapedContent).filter(
                and_(
                    ScrapedContent.keyword_search_id == keyword_search_id,
                    ScrapedContent.source == source,
                    ScrapedContent.source_id == source_id
                )
            ).first()
            
            return existing is not None
        finally:
            session.close()
    
    def mark_content_scraped(
        self,
        keyword_search_id: str,
        source: str,
        source_id: str,
        url: str,
        created_lead: bool = False
    ) -> ScrapedContent:
        """
        Mark content as scraped to prevent duplicate processing.
        
        Args:
            keyword_search_id: Keyword search ID
            source: Source platform
            source_id: Source ID
            url: Content URL
            created_lead: Whether a lead was created from this content
            
        Returns:
            ScrapedContent model
        """
        session = self.get_session()
        try:
            # Generate ID
            scraped_id = f"scraped_{uuid.uuid4().hex[:12]}"
            
            # Check if already exists (shouldn't happen due to unique constraint, but check anyway)
            existing = session.query(ScrapedContent).filter(
                and_(
                    ScrapedContent.keyword_search_id == keyword_search_id,
                    ScrapedContent.source == source,
                    ScrapedContent.source_id == source_id
                )
            ).first()
            
            if existing:
                # Update processed_at and created_lead
                existing.processed_at = datetime.utcnow()
                existing.created_lead = created_lead
                session.commit()
                session.refresh(existing)
                return existing
            
            # Create new
            scraped = ScrapedContent(
                id=scraped_id,
                keyword_search_id=keyword_search_id,
                source=source,
                source_id=source_id,
                url=url,
                processed_at=datetime.utcnow(),
                created_lead=created_lead
            )
            
            session.add(scraped)
            session.commit()
            session.refresh(scraped)
            
            logger.debug("Marked content as scraped", source_id=source_id, url=url)
            return scraped
            
        except Exception as e:
            session.rollback()
            logger.error("Failed to mark content as scraped", error=str(e))
            raise
        finally:
            session.close()
    
    def filter_already_scraped(
        self,
        keyword_search_id: str,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter out items that have already been scraped.
        
        Args:
            keyword_search_id: Keyword search ID
            items: List of items with 'source', 'id' or 'source_id', 'url' keys
            
        Returns:
            Filtered list of items not yet scraped
        """
        if not items:
            return []
        
        session = self.get_session()
        try:
            # Get all already scraped source_ids for this search
            scraped = session.query(ScrapedContent).filter(
                ScrapedContent.keyword_search_id == keyword_search_id
            ).all()
            
            scraped_ids = {
                (sc.source, sc.source_id) for sc in scraped
            }
            
            # Filter items
            new_items = []
            skipped_count = 0
            
            for item in items:
                source = item.get("source", "reddit")
                source_id = item.get("id") or item.get("source_id")
                
                if not source_id:
                    # Skip items without source_id
                    continue
                
                if (source, source_id) in scraped_ids:
                    skipped_count += 1
                    logger.debug("Skipping already scraped content", source_id=source_id)
                    continue
                
                new_items.append(item)
            
            if skipped_count > 0:
                logger.info(
                    "Filtered already scraped content",
                    total=len(items),
                    skipped=skipped_count,
                    new=len(new_items)
                )
            
            return new_items
            
        finally:
            session.close()
    
    # LLM Cache Operations
    
    def get_llm_cache(
        self,
        cache_key: str,
        cache_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LLM result.
        
        Args:
            cache_key: SHA256 hash of text content
            cache_type: "classification" or "info_extraction"
            
        Returns:
            Cached result dictionary or None if not found
        """
        session = self.get_session()
        try:
            cache_entry = session.query(LLMCache).filter(
                and_(
                    LLMCache.cache_key == cache_key,
                    LLMCache.cache_type == cache_type
                )
            ).first()
            
            if cache_entry:
                # Update usage stats
                cache_entry.last_used_at = datetime.utcnow()
                cache_entry.use_count += 1
                session.commit()
                
                logger.debug(
                    "LLM cache hit",
                    cache_type=cache_type,
                    use_count=cache_entry.use_count
                )
                return cache_entry.result
            
            return None
            
        finally:
            session.close()
    
    def set_llm_cache(
        self,
        cache_key: str,
        cache_type: str,
        result: Dict[str, Any],
        text_preview: Optional[str] = None
    ) -> LLMCache:
        """
        Store LLM result in cache.
        
        Args:
            cache_key: SHA256 hash of text content
            cache_type: "classification" or "info_extraction"
            result: LLM result dictionary
            text_preview: Preview of original text (truncated to 1000 chars)
            
        Returns:
            Created/updated LLMCache entry
        """
        session = self.get_session()
        try:
            # Truncate text preview if provided
            if text_preview and len(text_preview) > 1000:
                text_preview = text_preview[:1000]
            
            # Check if exists
            existing = session.query(LLMCache).filter(
                and_(
                    LLMCache.cache_key == cache_key,
                    LLMCache.cache_type == cache_type
                )
            ).first()
            
            if existing:
                # Update existing entry
                existing.result = result
                existing.last_used_at = datetime.utcnow()
                existing.text_preview = text_preview or existing.text_preview
                session.commit()
                session.refresh(existing)
                return existing
            
            # Create new entry
            cache_id = f"llm_cache_{uuid.uuid4().hex[:12]}"
            cache_entry = LLMCache(
                id=cache_id,
                cache_key=cache_key,
                cache_type=cache_type,
                result=result,
                text_preview=text_preview,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow(),
                use_count=1.0
            )
            
            session.add(cache_entry)
            session.commit()
            session.refresh(cache_entry)
            
            logger.debug("Stored LLM result in cache", cache_type=cache_type, cache_key=cache_key[:16])
            return cache_entry
            
        except Exception as e:
            session.rollback()
            logger.error("Failed to store LLM cache", error=str(e))
            raise
        finally:
            session.close()

