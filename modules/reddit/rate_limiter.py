"""
Global rate limiter for Reddit API calls.
Coordinates rate limiting across all scraper instances to prevent hitting Reddit's API limits.
"""

import asyncio
import time
from collections import deque
from typing import Optional

from core.config import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class GlobalRedditRateLimiter:
    """
    Global rate limiter for Reddit API calls.
    Tracks all API requests across all scraper instances to ensure we stay under Reddit's limits.
    """
    
    _instance: Optional['GlobalRedditRateLimiter'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        """Initialize global rate limiter."""
        self.config = get_config()
        self.max_requests_per_minute = self.config.reddit_max_requests_per_minute
        self.rate_limit_delay = self.config.reddit_rate_limit_delay
        
        # Track request timestamps (sliding window)
        self._request_timestamps: deque = deque()
        self._last_request_time = 0.0
        
        logger.info(
            "Initialized GlobalRedditRateLimiter",
            max_requests_per_minute=self.max_requests_per_minute,
            rate_limit_delay=self.rate_limit_delay
        )
    
    @classmethod
    def get_instance(cls) -> 'GlobalRedditRateLimiter':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def wait_if_needed(self) -> None:
        """
        Wait if needed to respect rate limits.
        This method:
        1. Enforces per-instance delay (rate_limit_delay)
        2. Enforces global rate limit (max_requests_per_minute)
        """
        async with self._lock:
            current_time = time.time()
            
            # Step 1: Enforce per-instance delay
            time_since_last = current_time - self._last_request_time
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                await asyncio.sleep(sleep_time)
                current_time = time.time()
            
            # Step 2: Enforce global rate limit (sliding window)
            # Remove timestamps older than 1 minute
            one_minute_ago = current_time - 60.0
            while self._request_timestamps and self._request_timestamps[0] < one_minute_ago:
                self._request_timestamps.popleft()
            
            # Check if we're at the limit
            if len(self._request_timestamps) >= self.max_requests_per_minute:
                # Calculate how long to wait
                oldest_request = self._request_timestamps[0]
                wait_time = 60.0 - (current_time - oldest_request) + 0.1  # Add 0.1s buffer
                
                if wait_time > 0:
                    logger.debug(
                        "Global rate limit reached, waiting",
                        wait_seconds=wait_time,
                        requests_in_window=len(self._request_timestamps)
                    )
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                    
                    # Clean up old timestamps again after waiting
                    one_minute_ago = current_time - 60.0
                    while self._request_timestamps and self._request_timestamps[0] < one_minute_ago:
                        self._request_timestamps.popleft()
            
            # Record this request
            self._request_timestamps.append(current_time)
            self._last_request_time = current_time
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        current_time = time.time()
        one_minute_ago = current_time - 60.0
        
        # Clean up old timestamps
        while self._request_timestamps and self._request_timestamps[0] < one_minute_ago:
            self._request_timestamps.popleft()
        
        return {
            "requests_in_last_minute": len(self._request_timestamps),
            "max_requests_per_minute": self.max_requests_per_minute,
            "rate_limit_delay": self.rate_limit_delay,
            "remaining_capacity": max(0, self.max_requests_per_minute - len(self._request_timestamps))
        }


# Global instance getter
def get_global_rate_limiter() -> GlobalRedditRateLimiter:
    """Get global Reddit rate limiter instance."""
    return GlobalRedditRateLimiter.get_instance()

