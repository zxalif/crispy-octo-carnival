"""
Scheduler for automated keyword search processing.
Uses APScheduler to periodically check and process due searches.
"""

import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import get_config
from core.logger import get_logger
from core.processor import process_keyword_search
from modules.database.storage import LeadStorage
from modules.keywords.manager import KeywordSearchManager
from modules.jobs.tracker import get_job_tracker

logger = get_logger(__name__)


class RixlyScheduler:
    """Scheduler for automated keyword search processing."""
    
    def __init__(self, storage: Optional[LeadStorage] = None):
        """
        Initialize scheduler.
        
        Args:
            storage: Optional LeadStorage instance
        """
        self.config = get_config()
        self.storage = storage or LeadStorage()
        self.manager = KeywordSearchManager(self.storage)
        self.scheduler = AsyncIOScheduler()
        self._running = False
        
        logger.info("Initialized RixlyScheduler")
    
    async def process_due_searches(self):
        """Process all keyword searches that are due for scraping."""
        try:
            # Get statistics about all searches
            all_searches = self.storage.list_keyword_searches(enabled_only=False, limit=1000)
            total_searches = len(all_searches)
            enabled_searches = sum(1 for s in all_searches if s.enabled)
            scheduled_searches = sum(1 for s in all_searches if s.scraping_mode == "scheduled" and s.enabled)
            
            logger.info(
                "Scheduler check started",
                total_searches=total_searches,
                enabled_searches=enabled_searches,
                scheduled_searches=scheduled_searches
            )
            
            # Get due searches
            due_searches = self.manager.get_due_searches()
            
            if not due_searches:
                logger.info(
                    "No keyword searches due for processing",
                    total_searches=total_searches,
                    enabled_searches=enabled_searches,
                    scheduled_searches=scheduled_searches,
                    reason="All scheduled searches are up to date or no scheduled searches exist"
                )
                return
            
            logger.info(
                "Found searches due for processing",
                due_count=len(due_searches),
                search_ids=[s.id for s in due_searches],
                search_names=[s.name for s in due_searches]
            )
            
            job_tracker = get_job_tracker(self.storage)
            
            # Track processing statistics
            processed_count = 0
            skipped_count = 0
            failed_count = 0
            total_leads_created = 0
            
            for search in due_searches:
                try:
                    # Check if job can be started (not running and cooldown passed)
                    can_start, reason = job_tracker.can_start_job(search.id)
                    
                    if not can_start:
                        skipped_count += 1
                        logger.info(
                            "Skipping search - job conflict or cooldown",
                            search_id=search.id,
                            search_name=search.name,
                            reason=reason,
                            next_scrape_at=search.next_scrape_at.isoformat() if search.next_scrape_at else None,
                            last_scrape_at=search.last_scrape_at.isoformat() if search.last_scrape_at else None
                        )
                        continue
                    
                    # Start job tracking
                    if not job_tracker.start_job(search.id):
                        logger.warning(
                            "Failed to start job for search",
                            search_id=search.id
                        )
                        continue
                    
                    logger.info(
                        "Starting keyword search processing",
                        search_id=search.id,
                        name=search.name,
                        platforms=search.platforms,
                        scraping_mode=search.scraping_mode,
                        scraping_interval=search.scraping_interval,
                        keywords_count=len(search.keywords),
                        patterns_count=len(search.patterns),
                        next_scrape_at=search.next_scrape_at.isoformat() if search.next_scrape_at else None
                    )
                    
                    # Update database with job status
                    try:
                        from core.state import KeywordSearchState
                        search_model = self.storage.get_keyword_search(search.id)
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
                            self.storage.save_keyword_search(search_state)
                    except Exception as e:
                        logger.warning("Failed to update job status in database", search_id=search.id, error=str(e))
                    
                    # Process the search
                    process_start_time = datetime.utcnow()
                    result = await process_keyword_search(search, self.storage)
                    process_duration = (datetime.utcnow() - process_start_time).total_seconds()
                    
                    # Extract result statistics
                    posts_scraped = result.get("posts_scraped", 0)
                    comments_scraped = result.get("comments_scraped", 0)
                    leads_created = result.get("leads_created", 0)
                    total_leads_created += leads_created
                    
                    # Mark as scraped and completed
                    self.manager.mark_scraped(search.id)
                    job_tracker.complete_job(search.id, success=True)
                    
                    # Update database with completion
                    try:
                        search_model = self.storage.get_keyword_search(search.id)
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
                            self.storage.save_keyword_search(search_state)
                    except Exception as e:
                        logger.warning("Failed to update completion status in database", search_id=search.id, error=str(e))
                    
                    processed_count += 1
                    logger.info(
                        "Completed keyword search processing",
                        search_id=search.id,
                        search_name=search.name,
                        posts_scraped=posts_scraped,
                        comments_scraped=comments_scraped,
                        leads_created=leads_created,
                        processing_time_seconds=round(process_duration, 2),
                        next_scrape_at=search.next_scrape_at.isoformat() if search.next_scrape_at else None
                    )
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    # Only complete job if we started tracking it
                    if job_tracker.is_job_running(search.id):
                        job_tracker.complete_job(search.id, success=False, error=error_msg)
                    
                    logger.error(
                        "Failed to process keyword search",
                        search_id=search.id,
                        search_name=search.name,
                        error=error_msg,
                        error_type=type(e).__name__
                    )
            
            # Log summary
            logger.info(
                "Scheduler check completed",
                total_due=len(due_searches),
                processed=processed_count,
                skipped=skipped_count,
                failed=failed_count,
                total_leads_created=total_leads_created,
                next_check_in_seconds=self.config.scheduler_check_interval
            )
                    
        except Exception as e:
            logger.error(
                "Failed to process due searches",
                error=str(e),
                error_type=type(e).__name__
            )
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        if not self.config.scheduler_enabled:
            logger.info("Scheduler is disabled in config")
            return
        
        # Schedule periodic check
        check_interval = self.config.scheduler_check_interval
        self.scheduler.add_job(
            self.process_due_searches,
            trigger=IntervalTrigger(seconds=check_interval),
            id="process_due_searches",
            name="Process due keyword searches",
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        self._running = True
        
        logger.info(
            "Started scheduler",
            check_interval=check_interval,
            enabled=self.config.scheduler_enabled
        )
    
    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        self.scheduler.shutdown()
        self._running = False
        
        logger.info("Stopped scheduler")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

