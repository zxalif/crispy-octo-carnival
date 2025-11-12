"""
Keyword matching for filtering content.
"""

import re
from typing import List, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class KeywordMatcher:
    """Matches keywords in text with word boundary matching."""
    
    def __init__(self, keywords: List[str], case_sensitive: bool = False):
        """
        Initialize keyword matcher.
        
        Args:
            keywords: List of keywords to match
            case_sensitive: Whether matching should be case-sensitive
        """
        self.keywords = [kw.strip() for kw in keywords if kw.strip()]
        self.case_sensitive = case_sensitive
        
        # Prepare keywords for matching with word boundaries
        self.prepared_keywords = self._prepare_keywords(self.keywords)
        
        logger.debug("Initialized KeywordMatcher", keyword_count=len(self.keywords))
    
    def _prepare_keywords(self, keywords: List[str]) -> List[Tuple[str, re.Pattern]]:
        """Prepare keywords for matching by creating regex patterns."""
        prepared = []
        for keyword in keywords:
            # Escape special regex characters
            escaped = re.escape(keyword)
            # Create word boundary pattern
            pattern = rf"\b{escaped}\b"
            flags = 0 if self.case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
            prepared.append((keyword, compiled))
        
        return prepared
    
    def match(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check if text contains any keywords.
        
        Args:
            text: Text to search
            
        Returns:
            Tuple of (has_match, matched_keywords)
        """
        if not text or not self.keywords:
            return False, []
        
        matched = []
        for keyword, pattern in self.prepared_keywords:
            if pattern.search(text):
                matched.append(keyword)
        
        return len(matched) > 0, matched
    
    def get_match_score(self, text: str) -> float:
        """
        Get match score based on keyword matches.
        
        Args:
            text: Text to score
            
        Returns:
            Match score (0.0 to 1.0)
        """
        if not text or not self.keywords:
            return 0.0
        
        _, matched = self.match(text)
        if not matched:
            return 0.0
        
        # Score based on percentage of keywords matched
        return len(matched) / len(self.keywords)

