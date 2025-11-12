"""
Reddit post and comment parser.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.logger import get_logger

logger = get_logger(__name__)


class RedditParser:
    """Parses Reddit posts and comments to extract useful information."""
    
    # Email regex pattern
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    # URL regex pattern
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    # Domain pattern (without http/https)
    DOMAIN_PATTERN = re.compile(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
    )
    
    def parse_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Reddit post and extract information.
        
        Args:
            post_data: Raw post data from scraper
            
        Returns:
            Parsed post data with extracted information
        """
        text = f"{post_data.get('title', '')} {post_data.get('content', '')}"
        
        parsed = post_data.copy()
        parsed.update({
            "emails": self.extract_emails(text),
            "urls": self.extract_urls(text),
            "domains": self.extract_domains(text),
            "has_contact_info": self._has_contact_info(text),
        })
        
        return parsed
    
    def parse_comment(self, comment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Reddit comment and extract information.
        
        Args:
            comment_data: Raw comment data from scraper
            
        Returns:
            Parsed comment data with extracted information
        """
        text = comment_data.get('content', '')
        
        parsed = comment_data.copy()
        parsed.update({
            "emails": self.extract_emails(text),
            "urls": self.extract_urls(text),
            "domains": self.extract_domains(text),
            "has_contact_info": self._has_contact_info(text),
        })
        
        return parsed
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        if not text:
            return []
        
        emails = self.EMAIL_PATTERN.findall(text)
        return list(set(emails))  # Remove duplicates
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        if not text:
            return []
        
        urls = self.URL_PATTERN.findall(text)
        return list(set(urls))
    
    def extract_domains(self, text: str) -> List[str]:
        """Extract domain names from text."""
        if not text:
            return []
        
        domains = set()
        
        # Extract from URLs
        urls = self.extract_urls(text)
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domains.add(parsed.netloc)
            except Exception:
                pass
        
        # Extract standalone domains
        standalone = self.DOMAIN_PATTERN.findall(text)
        domains.update(standalone)
        
        # Filter out common non-domain matches
        filtered = [
            d for d in domains
            if not any(x in d.lower() for x in ['reddit.com', 'imgur.com', 'youtube.com'])
        ]
        
        return list(filtered)
    
    def extract_company_name(self, text: str) -> Optional[str]:
        """Attempt to extract company name from text."""
        patterns = [
            r'\bat\s+([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp)?)',
            r'\bfor\s+([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp)?)',
            r'\bcompany:\s*([A-Z][A-Za-z0-9\s&]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                company = match.group(1).strip()
                if 2 < len(company) < 50:
                    return company
        
        return None
    
    def _has_contact_info(self, text: str) -> bool:
        """Check if text contains contact information."""
        has_email = len(self.extract_emails(text)) > 0
        has_domain = len(self.extract_domains(text)) > 0
        
        contact_keywords = ['email', 'contact', 'reach out', 'dm me', 'message me']
        has_contact_keyword = any(kw in text.lower() for kw in contact_keywords)
        
        return has_email or has_domain or has_contact_keyword

