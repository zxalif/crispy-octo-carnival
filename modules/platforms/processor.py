"""
Platform processor that routes to appropriate scrapers.
Future-proof for LinkedIn/Twitter.
"""

from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from modules.platforms.base import BasePlatformScraper
from modules.reddit.scraper import RedditScraper

logger = get_logger(__name__)


class PlatformProcessor:
    """Routes processing to appropriate platform scrapers."""
    
    def __init__(self):
        """Initialize platform processor."""
        self._scrapers: Dict[str, BasePlatformScraper] = {}
        logger.info("Initialized PlatformProcessor")
    
    def get_scraper(self, platform: str) -> BasePlatformScraper:
        """
        Get or create scraper for platform.
        
        Args:
            platform: Platform name ("reddit", "linkedin", "twitter")
            
        Returns:
            Platform scraper instance
        """
        if platform not in self._scrapers:
            if platform == "reddit":
                self._scrapers[platform] = RedditScraper()
            elif platform == "linkedin":
                # Future: self._scrapers[platform] = LinkedInScraper()
                raise NotImplementedError("LinkedIn scraper not yet implemented")
            elif platform == "twitter":
                # Future: self._scrapers[platform] = TwitterScraper()
                raise NotImplementedError("Twitter scraper not yet implemented")
            else:
                raise ValueError(f"Unknown platform: {platform}")
        
        return self._scrapers[platform]
    
    async def process_platform(
        self,
        platform: str,
        config: Dict[str, Any],
        include_comments: bool = True,
        search_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process a platform (scrape posts and optionally comments).
        
        Args:
            platform: Platform name
            config: Platform-specific configuration
            include_comments: Whether to scrape comments
            search_id: Optional search ID for metrics tracking
            
        Returns:
            Tuple of (posts, comments)
        """
        scraper = self.get_scraper(platform)
        
        if include_comments:
            posts, comments = await scraper.scrape_with_comments(config, search_id=search_id)
        else:
            posts = await scraper.scrape_posts(config, search_id=search_id)
            comments = []
        
        logger.info(
            "Processed platform",
            platform=platform,
            posts=len(posts),
            comments=len(comments),
            search_id=search_id
        )
        
        return posts, comments
    
    async def close_all(self):
        """Close all scraper connections."""
        for platform, scraper in self._scrapers.items():
            try:
                await scraper.close()
                logger.info(f"Closed {platform} scraper")
            except Exception as e:
                logger.warning(f"Error closing {platform} scraper", error=str(e))

