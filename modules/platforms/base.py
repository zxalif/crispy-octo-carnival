"""
Base scraper interface for platform-agnostic design.
Future-proof for LinkedIn/Twitter.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class BasePlatformScraper(ABC):
    """Base interface for all platform scrapers."""
    
    def __init__(self):
        """Initialize platform scraper."""
        self.platform_name = self.__class__.__name__.replace("Scraper", "").lower()
        logger.info(f"Initialized {self.platform_name} scraper")
    
    @abstractmethod
    async def scrape_posts(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts from the platform.
        
        Args:
            config: Platform-specific configuration
            
        Returns:
            List of post dictionaries
        """
        pass
    
    @abstractmethod
    async def scrape_comments(
        self,
        post_id: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Scrape comments from a post.
        
        Args:
            post_id: Post ID
            config: Platform-specific configuration
            
        Returns:
            List of comment dictionaries
        """
        pass
    
    @abstractmethod
    async def scrape_with_comments(
        self,
        config: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Scrape posts and their comments.
        
        Args:
            config: Platform-specific configuration
            
        Returns:
            Tuple of (posts, comments)
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close scraper connections."""
        pass

