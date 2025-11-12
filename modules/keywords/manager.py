"""
Keyword search manager for managing user-defined searches.
Simplified - works with database storage.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.logger import get_logger
from core.state import KeywordSearchState
from modules.database.storage import LeadStorage

logger = get_logger(__name__)


class KeywordSearchManager:
    """Manages keyword searches (uses database storage)."""
    
    def __init__(self, storage: Optional[LeadStorage] = None):
        """
        Initialize keyword search manager.
        
        Args:
            storage: LeadStorage instance (creates new if not provided)
        """
        self.storage = storage or LeadStorage()
        logger.info("Initialized KeywordSearchManager")
    
    def create_search(
        self,
        name: str,
        keywords: List[str],
        patterns: List[str],
        platforms: List[str],
        reddit_config: Optional[Dict] = None,
        scraping_mode: str = "scheduled",
        scraping_interval: Optional[str] = None,
        enabled: bool = True,
        webhook_url: Optional[str] = None
    ) -> KeywordSearchState:
        """
        Create a new keyword search.
        
        Args:
            name: Search name
            keywords: List of keywords to search for
            patterns: List of patterns to detect
            platforms: List of platforms (["reddit"])
            reddit_config: Reddit-specific config
            scraping_mode: "scheduled" or "one_time"
            scraping_interval: "30m", "1h", "6h", "24h" (only for scheduled)
            enabled: Whether search is enabled
            webhook_url: Optional webhook URL for notifications
            
        Returns:
            Created keyword search state
        """
        search_id = f"search_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        
        # Calculate next scrape time (if scheduled)
        next_scrape = None
        if scraping_mode == "scheduled" and scraping_interval:
            next_scrape = self._calculate_next_scrape(now, scraping_interval)
        
        search = KeywordSearchState(
            id=search_id,
            name=name,
            keywords=keywords,
            patterns=patterns,
            platforms=platforms,
            reddit_config=reddit_config,
            linkedin_config=None,  # Future
            twitter_config=None,  # Future
            scraping_mode=scraping_mode,
            scraping_interval=scraping_interval,
            enabled=enabled,
            webhook_url=webhook_url,
            created_at=now,
            updated_at=now,
            last_scrape_at=None,
            next_scrape_at=next_scrape
        )
        
        # Save to database
        self.storage.save_keyword_search(search)
        
        logger.info(
            "Created keyword search",
            search_id=search_id,
            name=name,
            platforms=platforms,
            scraping_mode=scraping_mode
        )
        
        return search
    
    def get_search(self, search_id: str) -> Optional[KeywordSearchState]:
        """Get a keyword search by ID."""
        search_model = self.storage.get_keyword_search(search_id)
        if not search_model:
            return None
        
        return self._model_to_state(search_model)
    
    def list_searches(
        self,
        enabled_only: bool = False
    ) -> List[KeywordSearchState]:
        """List all keyword searches."""
        search_models = self.storage.list_keyword_searches(enabled_only=enabled_only)
        return [self._model_to_state(m) for m in search_models]
    
    def update_search(
        self,
        search_id: str,
        **updates
    ) -> Optional[KeywordSearchState]:
        """Update a keyword search."""
        search = self.get_search(search_id)
        if not search:
            return None
        
        # Update fields
        for key, value in updates.items():
            if hasattr(search, key):
                setattr(search, key, value)
        
        # Recalculate next_scrape_at if interval changed
        if "scraping_interval" in updates and search.scraping_mode == "scheduled":
            if search.scraping_interval:
                search.next_scrape_at = self._calculate_next_scrape(
                    datetime.utcnow(),
                    search.scraping_interval
                )
            else:
                search.next_scrape_at = None
        
        search.updated_at = datetime.utcnow()
        
        # Save to database
        self.storage.save_keyword_search(search)
        
        logger.info("Updated keyword search", search_id=search_id, updates=updates)
        
        return search
    
    def delete_search(self, search_id: str) -> bool:
        """Delete a keyword search."""
        return self.storage.delete_keyword_search(search_id)
    
    def mark_scraped(self, search_id: str) -> None:
        """Mark a search as scraped and update next scrape time."""
        search = self.get_search(search_id)
        if not search:
            return
        
        now = datetime.utcnow()
        search.last_scrape_at = now
        
        if search.scraping_mode == "scheduled" and search.scraping_interval:
            search.next_scrape_at = self._calculate_next_scrape(now, search.scraping_interval)
        
        search.updated_at = now
        
        # Save to database
        self.storage.save_keyword_search(search)
        
        logger.info(
            "Marked search as scraped",
            search_id=search_id,
            next_scrape=search.next_scrape_at
        )
    
    def get_due_searches(self) -> List[KeywordSearchState]:
        """Get searches that are due for scraping."""
        search_models = self.storage.get_due_keyword_searches()
        return [self._model_to_state(m) for m in search_models]
    
    def _calculate_next_scrape(
        self,
        from_time: datetime,
        interval: str
    ) -> datetime:
        """Calculate next scrape time based on interval."""
        interval_map = {
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
        }
        
        delta = interval_map.get(interval, timedelta(hours=1))
        return from_time + delta
    
    def _model_to_state(self, model) -> KeywordSearchState:
        """Convert database model to KeywordSearchState."""
        return KeywordSearchState(
            id=model.id,
            name=model.name,
            keywords=model.keywords,
            patterns=model.patterns,
            platforms=model.platforms,
            reddit_config=model.reddit_config,
            linkedin_config=model.linkedin_config,
            twitter_config=model.twitter_config,
            scraping_mode=model.scraping_mode,
            scraping_interval=model.scraping_interval,
            enabled=model.enabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_scrape_at=model.last_scrape_at,
            next_scrape_at=model.next_scrape_at,
            scraping_status=getattr(model, "scraping_status", None),
            scraping_started_at=getattr(model, "scraping_started_at", None),
            scraping_completed_at=getattr(model, "scraping_completed_at", None),
            scraping_error=getattr(model, "scraping_error", None),
            webhook_url=getattr(model, "webhook_url", None)
        )

