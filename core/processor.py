"""
Main processing function for keyword searches.
Direct processing - no agent orchestration.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.state import KeywordSearchState, LeadState
from modules.platforms.processor import PlatformProcessor
from modules.reddit.filters import RedditFilter
from modules.reddit.parser import RedditParser
from modules.analyzer.lead_analyzer import LeadAnalyzer
from modules.database.storage import LeadStorage
from modules.keywords.manager import KeywordSearchManager
from modules.webhooks.sender import get_webhook_sender

logger = get_logger(__name__)


async def process_keyword_search(
    keyword_search: KeywordSearchState,
    storage: Optional[LeadStorage] = None
) -> Dict[str, Any]:
    """
    Main processing function for a keyword search.
    
    This function:
    1. Routes to appropriate platform scrapers
    2. Scrapes content (posts + comments)
    3. Filters by keywords/patterns
    4. Analyzes leads (classify, extract, score)
    5. Stores in database (linked to keyword_search)
    6. Updates keyword_search tracking
    7. Returns results
    
    Args:
        keyword_search: Keyword search to process
        storage: Optional LeadStorage instance
        
    Returns:
        Results dictionary with statistics and leads
    """
    start_time = time.time()
    storage = storage or LeadStorage()
    processor = PlatformProcessor()
    parser = RedditParser()
    filter_module = RedditFilter()
    analyzer = LeadAnalyzer(storage=storage)  # Pass storage for LLM caching
    manager = KeywordSearchManager(storage)
    
    all_posts = []
    all_comments = []
    all_leads = []
    
    try:
        # Step 1: Process each platform
        for platform in keyword_search.platforms:
            logger.info("Processing platform", platform=platform, search_id=keyword_search.id)
            
            # Get platform config
            if platform == "reddit":
                config = keyword_search.reddit_config or {}
                # Ensure subreddits are in config
                if "subreddits" not in config:
                    # Fallback: use subreddits from old structure if exists
                    # (for backward compatibility during migration)
                    config["subreddits"] = getattr(keyword_search, "subreddits", [])
                
                # Validate and enforce maximum limits
                from core.config import get_config
                max_config = get_config()
                
                # Validate post limit per subreddit
                post_limit = config.get("limit", 100)
                subreddits_list = config.get("subreddits", [])
                # If empty, we'll use r/all (count as 1 subreddit)
                num_subreddits = max(1, len(subreddits_list)) if subreddits_list else 1
                total_posts = post_limit * num_subreddits
                
                if total_posts > max_config.reddit_max_posts_per_search:
                    logger.warning(
                        "Post limit exceeds maximum, capping",
                        requested_total=total_posts,
                        max_allowed=max_config.reddit_max_posts_per_search,
                        subreddits=num_subreddits
                    )
                    # Cap per-subreddit limit to stay under total
                    max_per_subreddit = max(1, max_config.reddit_max_posts_per_search // num_subreddits)
                    config["limit"] = max_per_subreddit
                    logger.info(
                        "Adjusted post limit per subreddit",
                        new_limit=max_per_subreddit,
                        total_posts=max_per_subreddit * num_subreddits
                    )
                
                # Validate comment limit per post
                comment_limit = config.get("comment_limit", 100)
                if comment_limit > max_config.reddit_max_comments_per_post:
                    logger.warning(
                        "Comment limit exceeds maximum, capping",
                        requested=comment_limit,
                        max_allowed=max_config.reddit_max_comments_per_post
                    )
                    config["comment_limit"] = max_config.reddit_max_comments_per_post
            elif platform == "linkedin":
                config = keyword_search.linkedin_config or {}
            elif platform == "twitter":
                config = keyword_search.twitter_config or {}
            else:
                logger.warning("Unknown platform, skipping", platform=platform)
                continue
            
            # Scrape platform content
            posts, comments = await processor.process_platform(
                platform=platform,
                config=config,
                include_comments=config.get("include_comments", True),
                search_id=keyword_search.id
            )
            
            # Filter out already scraped content to prevent duplicates
            # This prevents re-scraping the same URLs/posts, saving API costs and preventing duplicates
            posts_before = len(posts)
            comments_before = len(comments)
            
            posts = storage.filter_already_scraped(keyword_search.id, posts)
            comments = storage.filter_already_scraped(keyword_search.id, comments)
            
            skipped_posts = posts_before - len(posts)
            skipped_comments = comments_before - len(comments)
            
            if skipped_posts > 0 or skipped_comments > 0:
                logger.info(
                    "Skipped already scraped content",
                    posts_skipped=skipped_posts,
                    comments_skipped=skipped_comments,
                    posts_new=len(posts),
                    comments_new=len(comments)
                )
            
            all_posts.extend(posts)
            all_comments.extend(comments)
        
        # Step 2: Parse content
        parsed_posts = [parser.parse_post(post) for post in all_posts]
        parsed_comments = [parser.parse_comment(comment) for comment in all_comments]
        
        # Step 3: Filter content
        filtered_posts = filter_module.filter_combined(
            items=parsed_posts,
            keywords=keyword_search.keywords,
            patterns=keyword_search.patterns,
            min_score=1,
            hours=24
        )
        
        filtered_comments = filter_module.filter_combined(
            items=parsed_comments,
            keywords=keyword_search.keywords,
            patterns=keyword_search.patterns,
            min_score=1,
            hours=24
        )
        
        # Step 4: Prepare lead data
        leads_data = []
        
        # Add posts
        for post in filtered_posts:
            leads_data.append({
                "title": post.get("title"),
                "content": post.get("content", ""),
                "author": post.get("author"),
                "url": post.get("url"),
                "source_id": post.get("id"),
                "source": "reddit",
                "source_type": "post",
                "author_profile_url": post.get("author_profile_url"),
                "matched_keywords": post.get("matched_keywords", []),
                "detected_pattern": post.get("detected_pattern"),
                "has_urgency": post.get("has_urgency", False),
                "created_utc": post.get("created_utc", datetime.utcnow()),
                "keyword_search_id": keyword_search.id
            })
        
        # Add comments
        for comment in filtered_comments:
            leads_data.append({
                "title": None,
                "content": comment.get("content", ""),
                "author": comment.get("author"),
                "url": comment.get("url"),
                "source_id": comment.get("id"),
                "source": "reddit",
                "source_type": "comment",
                "parent_post_id": comment.get("parent_post_id"),
                "author_profile_url": comment.get("author_profile_url"),
                "matched_keywords": comment.get("matched_keywords", []),
                "detected_pattern": comment.get("detected_pattern"),
                "has_urgency": comment.get("has_urgency", False),
                "created_utc": comment.get("created_utc", datetime.utcnow()),
                "keyword_search_id": keyword_search.id
            })
        
        # Step 5: Analyze leads
        analyzed_leads = analyzer.analyze_leads(
            leads_data=leads_data,
            total_keywords=len(keyword_search.keywords)
        )
        
        # Step 6: Store leads and mark content as scraped
        stored_leads = []
        webhook_sender = get_webhook_sender()
        
        for lead_state in analyzed_leads:
            
            # Save lead
            saved_lead = storage.save_lead(lead_state)
            if saved_lead:
                stored_leads.append(saved_lead)
                
                # TODO: for this keyword if there is no lead generated then in future there would be no lead as well
                # TODO: we have to make mark_content_scraped for all the leads for this keyword_searches
                # TODO: we might lose coments only but the leds would be reaming same?
                # Mark content as scraped
                storage.mark_content_scraped(
                    keyword_search_id=keyword_search.id,
                    source=lead_state.source,
                    source_id=lead_state.source_id,
                    url=lead_state.url,
                    created_lead=True
                )
                
                # Send webhook if configured
                if getattr(keyword_search, "webhook_url", None):
                    try:
                        await webhook_sender.send_lead_created(
                            webhook_url=keyword_search.webhook_url,
                            lead_data={
                                "id": saved_lead.id,
                                "title": saved_lead.title,
                                "url": saved_lead.url,
                                "author": saved_lead.author,
                                "opportunity_type": saved_lead.opportunity_type,
                                "opportunity_subtype": saved_lead.opportunity_subtype,
                                "total_score": saved_lead.total_score,
                                "status": saved_lead.status,
                                "source": saved_lead.source,
                                "source_type": saved_lead.source_type,
                                "created_at": saved_lead.created_at.isoformat()
                            },
                            keyword_search_id=keyword_search.id,
                            keyword_search_name=keyword_search.name
                        )
                    except Exception as e:
                        logger.warning("Failed to send webhook", error=str(e))
            
            # Mark as scraped even if not a lead (to prevent re-processing)
            # This handles cases where content was analyzed but didn't qualify as a lead
            if not saved_lead:
                # Find the original item to get URL
                url = lead_state.url
                for item in leads_data:
                    if item.get("source_id") == lead_state.source_id:
                        url = item.get("url", lead_state.url)
                        break
                
                storage.mark_content_scraped(
                    keyword_search_id=keyword_search.id,
                    source=lead_state.source,
                    source_id=lead_state.source_id,
                    url=url,
                    created_lead=False
                )
        
        all_leads.extend(stored_leads)
        
        # Step 7: Update keyword search
        keyword_search.last_scrape_at = datetime.utcnow()
        if keyword_search.scraping_mode == "scheduled" and keyword_search.scraping_interval:
            manager = KeywordSearchManager(storage)
            next_scrape = manager._calculate_next_scrape(
                datetime.utcnow(),
                keyword_search.scraping_interval
            )
            keyword_search.next_scrape_at = next_scrape
        
        storage.save_keyword_search(keyword_search)
        
        processing_time = time.time() - start_time
        
        # Step 8: Return results
        result = {
            "status": "success",
            "keyword_search_id": keyword_search.id,
            "platforms_processed": keyword_search.platforms,
            "posts_scraped": len(all_posts),
            "comments_scraped": len(all_comments),
            "posts_filtered": len(filtered_posts),
            "comments_filtered": len(filtered_comments),
            "leads_analyzed": len(analyzed_leads),
            "leads_created": len(stored_leads),
            "processing_time_seconds": round(processing_time, 2),
            "next_scrape_at": keyword_search.next_scrape_at.isoformat() if keyword_search.next_scrape_at else None,
            "leads": [
                {
                    "id": lead.id,
                    "source": lead.source,
                    "source_type": lead.source_type,
                    "title": lead.title,
                    "content": lead.content[:200] + "..." if len(lead.content) > 200 else lead.content,
                    "author": lead.author,
                    "url": lead.url,
                    "opportunity_type": lead.opportunity_type,
                    "opportunity_subtype": lead.opportunity_subtype,
                    "relevance_score": lead.relevance_score,
                    "urgency_score": lead.urgency_score,
                    "total_score": lead.total_score,
                    "status": lead.status,
                    "created_at": lead.created_at.isoformat()
                }
                for lead in stored_leads
            ]
        }
        
        logger.info(
            "Completed keyword search processing",
            search_id=keyword_search.id,
            leads_created=len(stored_leads),
            processing_time=processing_time
        )
        
        # Send job completion webhook if configured
        if getattr(keyword_search, "webhook_url", None):
            try:
                webhook_sender = get_webhook_sender()
                await webhook_sender.send_job_completed(
                    webhook_url=keyword_search.webhook_url,
                    keyword_search_id=keyword_search.id,
                    keyword_search_name=keyword_search.name,
                    stats={
                        "leads_created": len(stored_leads),
                        "posts_scraped": len(all_posts),
                        "comments_scraped": len(all_comments),
                        "processing_time_seconds": processing_time,
                        "completed_at": datetime.utcnow().isoformat()
                    }
                )
            except Exception as e:
                logger.warning("Failed to send job completion webhook", error=str(e))
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "Failed to process keyword search",
            search_id=keyword_search.id,
            error=error_msg
        )
        
        # Send job failure webhook if configured
        if getattr(keyword_search, "webhook_url", None):
            try:
                webhook_sender = get_webhook_sender()
                await webhook_sender.send_job_failed(
                    webhook_url=keyword_search.webhook_url,
                    keyword_search_id=keyword_search.id,
                    keyword_search_name=keyword_search.name,
                    error=error_msg
                )
            except Exception as webhook_error:
                logger.warning("Failed to send job failure webhook", error=str(webhook_error))
        
        return {
            "status": "error",
            "keyword_search_id": keyword_search.id,
            "error": error_msg,
            "posts_scraped": len(all_posts),
            "comments_scraped": len(all_comments),
            "leads_created": 0
        }
    
    finally:
        # Clean up
        await processor.close_all()

