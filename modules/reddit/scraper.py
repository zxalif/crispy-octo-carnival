"""
Reddit scraper using AsyncPRAW (Async Python Reddit API Wrapper).
Implements BasePlatformScraper interface.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpraw
from asyncpraw.models import Comment, Submission
from asyncprawcore.exceptions import RequestException, ServerError, ResponseException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

from core.config import get_config
from core.logger import get_logger
from modules.platforms.base import BasePlatformScraper
from modules.reddit.rate_limiter import get_global_rate_limiter
from modules.metrics.scraper_metrics import get_metrics_collector, ScrapingMetrics
from modules.vpn import ensure_vpn_connected

logger = get_logger(__name__)


class RedditScraper(BasePlatformScraper):
    """Scrapes Reddit for posts and comments."""
    
    def __init__(self):
        """Initialize Reddit scraper."""
        super().__init__()
        self.config = get_config()
        self._reddit: Optional[asyncpraw.Reddit] = None
        self._global_rate_limiter = get_global_rate_limiter()
        
        # Ensure VPN is connected if enabled (before any requests)
        if self.config.vpn_enabled:
            ensure_vpn_connected()
    
    @property
    def reddit(self) -> asyncpraw.Reddit:
        """Get or create Reddit client."""
        if self._reddit is None:
            if not self.config.reddit_client_id or not self.config.reddit_client_secret:
                raise ValueError("Reddit API credentials not configured")
            
            try:
                # Configure timeout for requests
                requestor_kwargs = {
                    "timeout": self.config.reddit_connection_timeout
                }
                
                self._reddit = asyncpraw.Reddit(
                    client_id=self.config.reddit_client_id,
                    client_secret=self.config.reddit_client_secret,
                    user_agent=self.config.reddit_user_agent,
                    requestor_kwargs=requestor_kwargs
                )
                
                logger.info(
                    "Initialized Async Reddit client",
                    user_agent=self.config.reddit_user_agent,
                    timeout=self.config.reddit_connection_timeout
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize Reddit client",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return self._reddit
    
    async def close(self):
        """Close Reddit client connection properly."""
        if self._reddit is not None:
            try:
                reddit_client = self._reddit
                self._reddit = None
                
                if hasattr(reddit_client, 'close'):
                    try:
                        if asyncio.iscoroutinefunction(reddit_client.close):
                            await reddit_client.close()
                        else:
                            reddit_client.close()
                    except Exception as close_error:
                        logger.warning(f"Error calling Reddit client close: {close_error}")
                
                logger.info("Closed Reddit client")
            except Exception as e:
                logger.warning(f"Error closing Reddit client: {e}")
    
    async def _rate_limit(self) -> None:
        """
        Apply rate limiting to respect Reddit API limits.
        Uses global rate limiter to coordinate across all scraper instances.
        """
        await self._global_rate_limiter.wait_if_needed()
    
    async def _scrape_subreddit_with_retry(
        self,
        subreddit_name: str,
        limit: int = 100,
        time_filter: str = "day",
        sort: str = "new"
    ) -> List[Dict[str, Any]]:
        """
        Internal method to scrape subreddit with retry logic.
        
        Args:
            subreddit_name: Name of subreddit
            limit: Maximum number of posts to fetch
            time_filter: Time filter (hour, day, week, month, year, all)
            sort: Sort method (hot, new, top, rising)
            
        Returns:
            List of post dictionaries
        """
        await self._rate_limit()
        
        subreddit = await self.reddit.subreddit(subreddit_name)
        
        # Get posts based on sort method
        if sort == "hot":
            posts = subreddit.hot(limit=limit)
        elif sort == "new":
            posts = subreddit.new(limit=limit)
        elif sort == "top":
            posts = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort == "rising":
            posts = subreddit.rising(limit=limit)
        else:
            posts = subreddit.new(limit=limit)
        
        scraped_posts = []
        async for post in posts:
            post_data = await self._extract_post_data(post)
            scraped_posts.append(post_data)
        
        return scraped_posts
    
    async def scrape_subreddit(
        self,
        subreddit_name: str,
        limit: int = 100,
        time_filter: str = "day",
        sort: str = "new",
        search_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts from a subreddit with retry logic for transient failures.
        
        Args:
            subreddit_name: Name of subreddit
            limit: Maximum number of posts to fetch
            time_filter: Time filter (hour, day, week, month, year, all)
            sort: Sort method (hot, new, top, rising)
            search_id: Optional search ID for metrics tracking
            
        Returns:
            List of post dictionaries
        """
        # Retry decorator for transient failures
        @retry(
            stop=stop_after_attempt(self.config.reddit_retry_attempts),
            wait=wait_exponential(
                multiplier=self.config.reddit_retry_delay,
                min=self.config.reddit_retry_delay,
                max=30.0
            ),
            retry=retry_if_exception_type((
                RequestException,
                ServerError,
                ResponseException,
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError
            )),
            reraise=True
        )
        async def _retry_scrape():
            return await self._scrape_subreddit_with_retry(
                subreddit_name=subreddit_name,
                limit=limit,
                time_filter=time_filter,
                sort=sort
            )
        
        retry_count = 0
        try:
            scraped_posts = await _retry_scrape()
            
            logger.info(
                "Scraped subreddit",
                subreddit=subreddit_name,
                post_count=len(scraped_posts),
                sort=sort,
                retries=retry_count
            )
            
            return scraped_posts
            
        except RetryError as e:
            # All retries exhausted
            retry_count = self.config.reddit_retry_attempts
            error = e.last_attempt.exception() if e.last_attempt else e
            
            import traceback
            logger.error(
                "Failed to scrape subreddit after retries",
                subreddit=subreddit_name,
                error=str(error),
                error_type=type(error).__name__,
                retries=retry_count,
                traceback=traceback.format_exc()
            )
            return []
            
        except Exception as e:
            import traceback
            
            underlying_error = None
            if isinstance(e, RequestException):
                if hasattr(e, 'original_exception'):
                    underlying_error = e.original_exception
                elif hasattr(e, 'cause') and e.__cause__:
                    underlying_error = e.__cause__
            
            error_details = {
                "subreddit": subreddit_name,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            
            if underlying_error:
                error_details["underlying_error"] = str(underlying_error)
                error_details["underlying_error_type"] = type(underlying_error).__name__
            
            logger.error(
                "Failed to scrape subreddit",
                **error_details,
                traceback=traceback.format_exc()
            )
            return []
    
    async def _scrape_post_comments_with_retry(
        self,
        post_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Internal method to scrape comments with retry logic.
        
        Args:
            post_id: Reddit post ID
            limit: Maximum number of comments (None for all)
            
        Returns:
            List of comment dictionaries
        """
        await self._rate_limit()
        
        submission = await self.reddit.submission(id=post_id)
        
        # Replace "MoreComments" objects with actual comments
        await submission.comments.replace_more(limit=0)
        
        comments = []
        comment_count = 0
        
        for comment in await submission.comments.list():
            if limit and comment_count >= limit:
                break
            
            if isinstance(comment, Comment):
                comment_data = await self._extract_comment_data(comment, post_id)
                comments.append(comment_data)
                comment_count += 1
        
        return comments
    
    async def scrape_post_comments(
        self,
        post_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape comments from a specific post with retry logic.
        
        Args:
            post_id: Reddit post ID
            limit: Maximum number of comments (None for all)
            
        Returns:
            List of comment dictionaries
        """
        # Retry decorator for transient failures
        @retry(
            stop=stop_after_attempt(self.config.reddit_retry_attempts),
            wait=wait_exponential(
                multiplier=self.config.reddit_retry_delay,
                min=self.config.reddit_retry_delay,
                max=30.0
            ),
            retry=retry_if_exception_type((
                RequestException,
                ServerError,
                ResponseException,
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError
            )),
            reraise=True
        )
        async def _retry_scrape():
            return await self._scrape_post_comments_with_retry(post_id, limit)
        
        try:
            comments = await _retry_scrape()
            
            logger.info(
                "Scraped post comments",
                post_id=post_id,
                comment_count=len(comments)
            )
            
            return comments
            
        except RetryError as e:
            error = e.last_attempt.exception() if e.last_attempt else e
            import traceback
            logger.error(
                "Failed to scrape post comments after retries",
                post_id=post_id,
                error=str(error),
                error_type=type(error).__name__,
                retries=self.config.reddit_retry_attempts,
                traceback=traceback.format_exc()
            )
            return []
            
        except Exception as e:
            import traceback
            logger.error(
                "Failed to scrape post comments",
                post_id=post_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc()
            )
            return []
    
    async def scrape_posts(
        self,
        config: Dict[str, Any],
        search_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts from Reddit (implements BasePlatformScraper).
        Implements partial result recovery - continues even if one subreddit fails.
        
        If subreddits is empty, searches across all of Reddit using r/all.
        
        Args:
            config: Reddit config with subreddits, limit, sort, etc.
            search_id: Optional search ID for metrics tracking
            
        Returns:
            List of post dictionaries
        """
        subreddits = config.get("subreddits", [])
        limit = config.get("limit", 100)
        sort = config.get("sort", "new")
        time_filter = config.get("time_filter", "day")
        
        # If no subreddits specified, search all of Reddit
        if not subreddits or len(subreddits) == 0:
            subreddits = ["all"]
            logger.info("No subreddits specified, searching all of Reddit", search_id=search_id)
        
        all_posts = []
        metrics_collector = get_metrics_collector()
        
        for subreddit in subreddits:
            metrics = ScrapingMetrics(
                search_id=search_id or "unknown",
                platform="reddit",
                subreddit=subreddit,
                start_time=datetime.utcnow()
            )
            
            try:
                posts = await self.scrape_subreddit(
                    subreddit_name=subreddit,
                    limit=limit,
                    time_filter=time_filter,
                    sort=sort,
                    search_id=search_id
                )
                
                metrics.posts_scraped = len(posts)
                metrics.subreddits_succeeded = 1
                all_posts.extend(posts)
                
                logger.info(
                    "Successfully scraped subreddit",
                    subreddit=subreddit,
                    posts=len(posts),
                    total_posts=len(all_posts)
                )
                
            except Exception as e:
                metrics.posts_failed = limit  # Estimate
                metrics.subreddits_failed = 1
                metrics.errors.append(f"{type(e).__name__}: {str(e)}")
                
                logger.warning(
                    "Failed to scrape subreddit, continuing with others",
                    subreddit=subreddit,
                    error=str(e),
                    total_posts_so_far=len(all_posts)
                )
            
            finally:
                metrics.end_time = datetime.utcnow()
                metrics_collector.record_metrics(metrics)
        
        logger.info(
            "Completed scraping posts",
            subreddits_attempted=len(subreddits),
            total_posts=len(all_posts)
        )
        
        return all_posts
    
    async def scrape_comments(
        self,
        post_id: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Scrape comments from a post (implements BasePlatformScraper).
        
        Args:
            post_id: Post ID
            config: Reddit config with comment_limit
            
        Returns:
            List of comment dictionaries
        """
        comment_limit = config.get("comment_limit", 100)
        return await self.scrape_post_comments(post_id, limit=comment_limit)
    
    async def scrape_with_comments(
        self,
        config: Dict[str, Any],
        search_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Scrape posts and comments (implements BasePlatformScraper).
        Implements partial result recovery - continues even if one subreddit/post fails.
        
        If subreddits is empty, searches across all of Reddit using r/all.
        
        Args:
            config: Reddit config
            search_id: Optional search ID for metrics tracking
            
        Returns:
            Tuple of (posts, comments)
        """
        include_comments = config.get("include_comments", True)
        subreddits = config.get("subreddits", [])
        post_limit = config.get("limit", 100)
        comment_limit = config.get("comment_limit", 100)
        sort = config.get("sort", "new")
        time_filter = config.get("time_filter", "day")
        
        # If no subreddits specified, search all of Reddit
        if not subreddits or len(subreddits) == 0:
            subreddits = ["all"]
            logger.info("No subreddits specified, searching all of Reddit", search_id=search_id)
        
        all_posts = []
        all_comments = []
        metrics_collector = get_metrics_collector()
        
        for subreddit in subreddits:
            metrics = ScrapingMetrics(
                search_id=search_id or "unknown",
                platform="reddit",
                subreddit=subreddit,
                start_time=datetime.utcnow()
            )
            
            try:
                # Scrape posts for this subreddit
                posts = await self.scrape_subreddit(
                    subreddit_name=subreddit,
                    limit=post_limit,
                    time_filter=time_filter,
                    sort=sort,
                    search_id=search_id
                )
                all_posts.extend(posts)
                metrics.posts_scraped = len(posts)
                
                # Scrape comments if enabled
                if include_comments:
                    for post in posts:
                        try:
                            comments = await self.scrape_post_comments(
                                post_id=post["id"],
                                limit=comment_limit
                            )
                            all_comments.extend(comments)
                            metrics.comments_scraped += len(comments)
                        except Exception as e:
                            metrics.comments_failed += 1
                            metrics.errors.append(f"Post {post['id']}: {str(e)}")
                            logger.warning(
                                "Failed to scrape comments for post, continuing",
                                post_id=post["id"],
                                subreddit=subreddit,
                                error=str(e)
                            )
                
                metrics.subreddits_succeeded = 1
                
                logger.info(
                    "Successfully scraped subreddit with comments",
                    subreddit=subreddit,
                    posts=len(posts),
                    comments=metrics.comments_scraped,
                    total_posts=len(all_posts),
                    total_comments=len(all_comments)
                )
                
            except Exception as e:
                metrics.posts_failed = post_limit  # Estimate
                metrics.subreddits_failed = 1
                metrics.errors.append(f"{type(e).__name__}: {str(e)}")
                
                logger.warning(
                    "Failed to scrape subreddit, continuing with others",
                    subreddit=subreddit,
                    error=str(e),
                    total_posts_so_far=len(all_posts),
                    total_comments_so_far=len(all_comments)
                )
            
            finally:
                metrics.end_time = datetime.utcnow()
                metrics_collector.record_metrics(metrics)
        
        logger.info(
            "Completed scraping with comments",
            subreddits_attempted=len(subreddits),
            total_posts=len(all_posts),
            total_comments=len(all_comments)
        )
        
        return all_posts, all_comments
    
    async def scrape_subreddit_with_comments(
        self,
        subreddit_name: str,
        post_limit: int = 50,
        comment_limit: int = 100,
        time_filter: str = "day",
        sort: str = "new"
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Scrape posts and their comments from a subreddit.
        
        Args:
            subreddit_name: Name of subreddit
            post_limit: Maximum number of posts
            comment_limit: Maximum number of comments per post
            time_filter: Time filter for posts
            sort: Sort method for posts
            
        Returns:
            Tuple of (posts, comments)
        """
        posts = await self.scrape_subreddit(
            subreddit_name=subreddit_name,
            limit=post_limit,
            time_filter=time_filter,
            sort=sort
        )
        
        all_comments = []
        for post in posts:
            comments = await self.scrape_post_comments(
                post_id=post["id"],
                limit=comment_limit
            )
            all_comments.extend(comments)
        
        logger.info(
            "Scraped subreddit with comments",
            subreddit=subreddit_name,
            post_count=len(posts),
            comment_count=len(all_comments)
        )
        
        return posts, all_comments
    
    async def _extract_post_data(self, post: Submission) -> Dict[str, Any]:
        """Extract data from a Reddit post."""
        author_name = str(post.author) if post.author else "[deleted]"
        author_profile_url = None
        
        if post.author and str(post.author) != "[deleted]":
            author_profile_url = f"https://www.reddit.com/user/{post.author}"
        
        return {
            "id": post.id,
            "title": post.title,
            "content": post.selftext,
            "author": author_name,
            "author_profile_url": author_profile_url,
            "subreddit": str(post.subreddit),
            "url": f"https://reddit.com{post.permalink}",
            "score": post.score,
            "num_comments": post.num_comments,
            "created_utc": datetime.fromtimestamp(post.created_utc),
            "is_self": post.is_self,
            "link_url": post.url if not post.is_self else None,
            "source": "reddit",
            "source_type": "post"
        }
    
    async def _extract_comment_data(self, comment: Comment, post_id: str) -> Dict[str, Any]:
        """Extract data from a Reddit comment."""
        author_name = str(comment.author) if comment.author else "[deleted]"
        author_profile_url = None
        
        if comment.author and str(comment.author) != "[deleted]":
            author_profile_url = f"https://www.reddit.com/user/{comment.author}"
        
        return {
            "id": comment.id,
            "content": comment.body,
            "author": author_name,
            "author_profile_url": author_profile_url,
            "subreddit": str(comment.subreddit),
            "url": f"https://reddit.com{comment.permalink}",
            "score": comment.score,
            "created_utc": datetime.fromtimestamp(comment.created_utc),
            "parent_post_id": post_id,
            "parent_id": comment.parent_id,
            "is_top_level": comment.parent_id.startswith("t3_"),
            "source": "reddit",
            "source_type": "comment"
        }

