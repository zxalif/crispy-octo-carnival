"""
Scraping metrics tracking for monitoring and observability.
Tracks success rates, error rates, and performance metrics.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapingMetrics:
    """Metrics for a single scraping operation."""
    
    search_id: str
    platform: str
    subreddit: Optional[str] = None
    
    # Counts
    posts_scraped: int = 0
    comments_scraped: int = 0
    posts_failed: int = 0
    comments_failed: int = 0
    subreddits_succeeded: int = 0
    subreddits_failed: int = 0
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    # Retry stats
    retry_count: int = 0
    
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        total = self.posts_scraped + self.posts_failed + self.comments_scraped + self.comments_failed
        if total == 0:
            return 1.0
        successful = self.posts_scraped + self.comments_scraped
        return successful / total
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "search_id": self.search_id,
            "platform": self.platform,
            "subreddit": self.subreddit,
            "posts_scraped": self.posts_scraped,
            "comments_scraped": self.comments_scraped,
            "posts_failed": self.posts_failed,
            "comments_failed": self.comments_failed,
            "subreddits_succeeded": self.subreddits_succeeded,
            "subreddits_failed": self.subreddits_failed,
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate(),
            "retry_count": self.retry_count,
            "error_count": len(self.errors),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class ScrapingMetricsCollector:
    """
    Collects and aggregates scraping metrics.
    Tracks metrics per search, per platform, and globally.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        # Store recent metrics (last 24 hours)
        self._recent_metrics: List[ScrapingMetrics] = []
        self._metrics_by_search: Dict[str, List[ScrapingMetrics]] = defaultdict(list)
        self._metrics_by_platform: Dict[str, List[ScrapingMetrics]] = defaultdict(list)
        
        logger.info("Initialized ScrapingMetricsCollector")
    
    def record_metrics(self, metrics: ScrapingMetrics):
        """
        Record scraping metrics.
        
        Args:
            metrics: Scraping metrics to record
        """
        # Set end time if not set
        if not metrics.end_time:
            metrics.end_time = datetime.utcnow()
        
        # Calculate duration
        if metrics.start_time and metrics.end_time:
            metrics.duration_seconds = (metrics.end_time - metrics.start_time).total_seconds()
        
        # Store metrics
        self._recent_metrics.append(metrics)
        self._metrics_by_search[metrics.search_id].append(metrics)
        self._metrics_by_platform[metrics.platform].append(metrics)
        
        # Clean up old metrics (older than 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self._recent_metrics = [
            m for m in self._recent_metrics
            if m.start_time and m.start_time >= cutoff
        ]
        
        logger.info(
            "Recorded scraping metrics",
            search_id=metrics.search_id,
            platform=metrics.platform,
            posts_scraped=metrics.posts_scraped,
            comments_scraped=metrics.comments_scraped,
            success_rate=metrics.success_rate(),
            duration_seconds=metrics.duration_seconds
        )
    
    def get_search_metrics(self, search_id: str) -> List[ScrapingMetrics]:
        """Get all metrics for a search."""
        return self._metrics_by_search.get(search_id, [])
    
    def get_platform_metrics(self, platform: str) -> List[ScrapingMetrics]:
        """Get all metrics for a platform."""
        return self._metrics_by_platform.get(platform, [])
    
    def get_recent_metrics(self, hours: int = 24) -> List[ScrapingMetrics]:
        """Get recent metrics within specified hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            m for m in self._recent_metrics
            if m.start_time and m.start_time >= cutoff
        ]
    
    def get_summary_stats(self, hours: int = 24) -> Dict:
        """
        Get summary statistics for recent scraping activity.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with summary statistics
        """
        recent = self.get_recent_metrics(hours)
        
        if not recent:
            return {
                "total_scrapes": 0,
                "total_posts_scraped": 0,
                "total_comments_scraped": 0,
                "total_errors": 0,
                "average_success_rate": 1.0,
                "average_duration_seconds": 0.0,
                "total_retries": 0
            }
        
        total_posts = sum(m.posts_scraped for m in recent)
        total_comments = sum(m.comments_scraped for m in recent)
        total_errors = sum(len(m.errors) for m in recent)
        total_retries = sum(m.retry_count for m in recent)
        
        success_rates = [m.success_rate() for m in recent]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 1.0
        
        durations = [m.duration_seconds for m in recent if m.duration_seconds > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        return {
            "total_scrapes": len(recent),
            "total_posts_scraped": total_posts,
            "total_comments_scraped": total_comments,
            "total_errors": total_errors,
            "average_success_rate": round(avg_success_rate, 3),
            "average_duration_seconds": round(avg_duration, 2),
            "total_retries": total_retries,
            "time_period_hours": hours
        }
    
    def get_platform_summary(self, platform: str, hours: int = 24) -> Dict:
        """Get summary statistics for a specific platform."""
        platform_metrics = self.get_platform_metrics(platform)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [
            m for m in platform_metrics
            if m.start_time and m.start_time >= cutoff
        ]
        
        if not recent:
            return {
                "platform": platform,
                "total_scrapes": 0,
                "total_posts_scraped": 0,
                "total_comments_scraped": 0,
                "average_success_rate": 1.0
            }
        
        total_posts = sum(m.posts_scraped for m in recent)
        total_comments = sum(m.comments_scraped for m in recent)
        success_rates = [m.success_rate() for m in recent]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 1.0
        
        return {
            "platform": platform,
            "total_scrapes": len(recent),
            "total_posts_scraped": total_posts,
            "total_comments_scraped": total_comments,
            "average_success_rate": round(avg_success_rate, 3),
            "time_period_hours": hours
        }


# Global metrics collector instance
_metrics_collector: Optional[ScrapingMetricsCollector] = None


def get_metrics_collector() -> ScrapingMetricsCollector:
    """Get or create global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = ScrapingMetricsCollector()
    return _metrics_collector

