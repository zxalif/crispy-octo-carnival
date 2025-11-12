"""
Filters for Reddit posts and comments.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from modules.keywords.matching import KeywordMatcher
from modules.keywords.patterns import PatternDetector

logger = get_logger(__name__)


class RedditFilter:
    """Filters Reddit posts and comments based on various criteria."""
    
    def __init__(self):
        """Initialize Reddit filter."""
        logger.info("Initialized RedditFilter")
    
    def filter_by_keywords(
        self,
        items: List[Dict[str, Any]],
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Filter items by keyword match."""
        if not keywords:
            return items
        
        matcher = KeywordMatcher(keywords)
        filtered = []
        
        for item in items:
            # Get text content
            if item.get('source_type') == 'post':
                text = f"{item.get('title', '')} {item.get('content', '')}"
            else:
                text = item.get('content', '')
            
            # Check for match
            has_match, matched = matcher.match(text)
            if has_match:
                item['matched_keywords'] = matched
                item['match_score'] = matcher.get_match_score(text)
                filtered.append(item)
        
        logger.info(
            "Filtered by keywords",
            total=len(items),
            matched=len(filtered)
        )
        
        return filtered
    
    def filter_by_patterns(
        self,
        items: List[Dict[str, Any]],
        patterns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Filter items by pattern detection."""
        detector = PatternDetector(custom_patterns=patterns)
        filtered = []
        
        for item in items:
            # Get text content
            if item.get('source_type') == 'post':
                text = f"{item.get('title', '')} {item.get('content', '')}"
            else:
                text = item.get('content', '')
            
            # Check for pattern
            has_pattern, matched_pattern = detector.detect(text)
            if has_pattern:
                item['detected_pattern'] = matched_pattern
                item['has_urgency'] = detector.has_urgency(text)
                filtered.append(item)
        
        logger.info(
            "Filtered by patterns",
            total=len(items),
            matched=len(filtered)
        )
        
        return filtered
    
    def filter_combined(
        self,
        items: List[Dict[str, Any]],
        keywords: List[str],
        patterns: Optional[List[str]] = None,
        min_score: int = 1,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Apply multiple filters with OR logic for keywords/patterns.
        
        Args:
            items: List of posts or comments
            keywords: Keywords to match
            patterns: Optional custom patterns
            min_score: Minimum score threshold
            hours: Number of hours to look back
            
        Returns:
            Filtered list
        """
        # Apply time and score filters first
        filtered = items
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = [
            item for item in filtered
            if item.get('created_utc', datetime.min) >= cutoff
        ]
        
        filtered = [
            item for item in filtered
            if item.get('score', 0) >= min_score
        ]
        
        # Apply keyword OR pattern matching (not AND)
        keyword_matches = self.filter_by_keywords(filtered, keywords=keywords)
        pattern_matches = self.filter_by_patterns(filtered, patterns=patterns) if patterns else []
        
        # Combine using OR logic (union of both sets)
        combined_ids = set()
        final_filtered = []
        
        for item in keyword_matches + pattern_matches:
            item_id = item.get('id')
            if item_id and item_id not in combined_ids:
                combined_ids.add(item_id)
                final_filtered.append(item)
        
        logger.info(
            "Applied combined filters (OR logic)",
            original=len(items),
            after_time_score=len(filtered),
            keyword_matches=len(keyword_matches),
            pattern_matches=len(pattern_matches),
            final=len(final_filtered)
        )
        
        return final_filtered

