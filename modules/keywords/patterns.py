"""
Pattern detection for identifying "looking for X" posts and comments.
"""

import re
from typing import List, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class PatternDetector:
    """Detects patterns like 'looking for', 'need', 'hiring' in text."""
    
    # Common patterns that indicate someone is looking for something
    PATTERNS = [
        # Direct patterns
        r"\blooking\s+for\b",
        r"\bneed\s+(?:a|an|some)?\b",
        r"\bsearching\s+for\b",
        r"\bseeking\s+(?:a|an)?\b",
        r"\bwant\s+(?:a|an|to\s+hire)?\b",
        r"\bhiring\b",
        r"\brecruiting\b",
        
        # Question patterns
        r"\b(?:anyone|does\s+anyone)\s+know\s+(?:a|an|of)?\b",
        r"\brecommendations?\s+for\b",
        r"\bcan\s+(?:anyone|someone)\s+recommend\b",
        r"\bwhere\s+(?:can\s+i|to)\s+find\b",
        r"\bwho\s+(?:can|should)\s+i\s+(?:hire|contact)\b",
        
        # Urgency patterns
        r"\bneed\s+(?:urgently|asap|immediately)\b",
        r"\burgent(?:ly)?\s+need\b",
        r"\basap\b",
        
        # Request patterns
        r"\btrying\s+to\s+find\b",
        r"\bin\s+(?:need|search)\s+of\b",
        r"\brequire\s+(?:a|an)?\b",
        r"\bmust\s+(?:find|hire)\b",
    ]
    
    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize pattern detector.
        
        Args:
            custom_patterns: Additional custom patterns to detect
        """
        self.patterns = self.PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        
        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.patterns
        ]
        
        logger.info("Initialized PatternDetector", pattern_count=len(self.patterns))
    
    def detect(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if text contains any of the patterns.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (pattern_found, matched_pattern)
        """
        if not text:
            return False, None
        
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                logger.debug("Pattern detected", pattern=matched_text, text_preview=text[:100])
                return True, matched_text
        
        return False, None
    
    def detect_all(self, text: str) -> List[str]:
        """
        Detect all patterns in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of all matched patterns
        """
        if not text:
            return []
        
        matches = []
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                matches.append(match.group(0))
        
        return matches
    
    def has_urgency(self, text: str) -> bool:
        """
        Check if text contains urgency indicators.
        
        Args:
            text: Text to analyze
            
        Returns:
            True if urgency detected
        """
        urgency_patterns = [
            r"\burgent(?:ly)?\b",
            r"\basap\b",
            r"\bimmediately\b",
            r"\bquickly\b",
            r"\bsoon\b",
            r"\bdeadline\b",
            r"\btime[-\s]sensitive\b",
        ]
        
        for pattern in urgency_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False

