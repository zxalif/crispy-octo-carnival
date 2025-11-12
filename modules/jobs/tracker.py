"""
Job tracking for keyword search scraping.
Prevents concurrent scrapes and enforces cooldown periods.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from core.config import get_config
from core.logger import get_logger
from modules.database.storage import LeadStorage

logger = get_logger(__name__)


class JobTracker:
    """Tracks scraping jobs to prevent conflicts and enforce cooldowns."""
    
    # In-memory tracking of active jobs
    _active_jobs: Dict[str, Dict] = {}
    
    # Default cooldown period (minimum time between scrapes)
    # Can be overridden via config
    
    def __init__(self, storage: Optional[LeadStorage] = None):
        """
        Initialize job tracker.
        
        Args:
            storage: Optional LeadStorage instance
        """
        self.config = get_config()
        self.storage = storage or LeadStorage()
        self.cooldown_minutes = self.config.job_cooldown_minutes
        logger.info("Initialized JobTracker", cooldown_minutes=self.cooldown_minutes)
    
    def is_job_running(self, search_id: str) -> bool:
        """
        Check if a job is currently running for a search.
        
        Args:
            search_id: Keyword search ID
            
        Returns:
            True if job is running
        """
        if search_id in self._active_jobs:
            job = self._active_jobs[search_id]
            # Check if job is still active (not completed/failed)
            if job.get("status") in ["running", "starting"]:
                # Check if job hasn't timed out (max 2 hours)
                started_at = job.get("started_at")
                if started_at:
                    elapsed = (datetime.utcnow() - started_at).total_seconds()
                    if elapsed > 7200:  # 2 hours timeout
                        logger.warning(
                            "Job timed out, marking as failed",
                            search_id=search_id,
                            elapsed_hours=elapsed / 3600
                        )
                        self._mark_job_failed(search_id, "Job timed out after 2 hours")
                        return False
                return True
        return False
    
    def can_start_job(
        self,
        search_id: str,
        min_cooldown_minutes: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a job can be started (not running and cooldown passed).
        
        Args:
            search_id: Keyword search ID
            min_cooldown_minutes: Minimum cooldown in minutes (uses default if None)
            
        Returns:
            Tuple of (can_start, reason_if_not)
        """
        # Check if job is already running
        if self.is_job_running(search_id):
            return False, f"Job already running for search {search_id}"
        
        # Check cooldown period
        cooldown = min_cooldown_minutes or self.cooldown_minutes
        search = self.storage.get_keyword_search(search_id)
        
        if search and search.last_scrape_at:
            time_since_last = datetime.utcnow() - search.last_scrape_at
            minutes_since = time_since_last.total_seconds() / 60
            
            if minutes_since < cooldown:
                remaining = cooldown - minutes_since
                return False, f"Cooldown period not met. Wait {remaining:.1f} more minutes"
        
        return True, None
    
    def start_job(self, search_id: str) -> bool:
        """
        Mark a job as started.
        
        Args:
            search_id: Keyword search ID
            
        Returns:
            True if job was started, False if already running
        """
        if self.is_job_running(search_id):
            logger.warning("Attempted to start job that's already running", search_id=search_id)
            return False
        
        self._active_jobs[search_id] = {
            "status": "running",
            "started_at": datetime.utcnow(),
            "search_id": search_id
        }
        
        logger.info("Started job", search_id=search_id)
        return True
    
    def complete_job(self, search_id: str, success: bool = True, error: Optional[str] = None):
        """
        Mark a job as completed.
        
        Args:
            search_id: Keyword search ID
            success: Whether job completed successfully
            error: Error message if failed
        """
        if search_id not in self._active_jobs:
            logger.warning("Attempted to complete job that wasn't tracked", search_id=search_id)
            return
        
        job = self._active_jobs[search_id]
        job["status"] = "completed" if success else "failed"
        job["completed_at"] = datetime.utcnow()
        job["success"] = success
        
        if error:
            job["error"] = error
        
        # Calculate duration
        if job.get("started_at"):
            duration = (job["completed_at"] - job["started_at"]).total_seconds()
            job["duration_seconds"] = duration
        
        logger.info(
            "Completed job",
            search_id=search_id,
            success=success,
            duration_seconds=job.get("duration_seconds")
        )
        
        # Keep job in memory for a short time (5 minutes) for debugging
        # Then remove it
        asyncio.create_task(self._cleanup_job(search_id, delay_seconds=300))
    
    def _mark_job_failed(self, search_id: str, error: str):
        """Mark a job as failed."""
        if search_id in self._active_jobs:
            self._active_jobs[search_id]["status"] = "failed"
            self._active_jobs[search_id]["error"] = error
            self._active_jobs[search_id]["completed_at"] = datetime.utcnow()
    
    async def _cleanup_job(self, search_id: str, delay_seconds: int = 300):
        """Remove job from tracking after delay."""
        await asyncio.sleep(delay_seconds)
        if search_id in self._active_jobs:
            job = self._active_jobs[search_id]
            if job.get("status") in ["completed", "failed"]:
                del self._active_jobs[search_id]
                logger.debug("Cleaned up completed job", search_id=search_id)
    
    def get_job_status(self, search_id: str) -> Optional[Dict]:
        """
        Get current job status for a search.
        
        Args:
            search_id: Keyword search ID
            
        Returns:
            Job status dict or None if no job
        """
        if search_id not in self._active_jobs:
            return None
        
        job = self._active_jobs[search_id].copy()
        
        # Calculate elapsed time if running
        if job.get("status") == "running" and job.get("started_at"):
            elapsed = (datetime.utcnow() - job["started_at"]).total_seconds()
            job["elapsed_seconds"] = elapsed
        
        return job
    
    def get_all_active_jobs(self) -> Dict[str, Dict]:
        """Get all currently active jobs."""
        return {
            search_id: job
            for search_id, job in self._active_jobs.items()
            if job.get("status") in ["running", "starting"]
        }


# Global job tracker instance
_job_tracker: Optional[JobTracker] = None


def get_job_tracker(storage: Optional[LeadStorage] = None) -> JobTracker:
    """Get or create global job tracker instance."""
    global _job_tracker
    if _job_tracker is None:
        _job_tracker = JobTracker(storage)
    return _job_tracker

