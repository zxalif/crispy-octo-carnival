"""
Contact information extractor.
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from core.logger import get_logger

logger = get_logger(__name__)


class ContactExtractor:
    """Extracts contact information from text."""
    
    # Email regex
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    # URL regex
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    # Domain pattern
    DOMAIN_PATTERN = re.compile(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
    )
    
    # Social media patterns
    TWITTER_PATTERN = re.compile(
        r'(?:twitter\.com|x\.com)/(?:@)?([a-zA-Z0-9_]+)',
        re.IGNORECASE
    )
    
    LINKEDIN_PATTERN = re.compile(
        r'linkedin\.com/(?:in|company)/([a-zA-Z0-9\-]+)',
        re.IGNORECASE
    )
    
    GITHUB_PATTERN = re.compile(
        r'github\.com/([a-zA-Z0-9\-]+)',
        re.IGNORECASE
    )
    
    # Company patterns
    COMPANY_PATTERNS = [
        r'\bat\s+([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp|Corporation|Company)?\.?)',
        r'\bfor\s+([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp|Corporation|Company)?\.?)',
        r'\bcompany:\s*([A-Z][A-Za-z0-9\s&]+)',
        r'\b([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp|Corporation|Company)\.?)\b',
    ]
    
    def __init__(self):
        """Initialize contact extractor."""
        logger.info("Initialized ContactExtractor")
    
    def extract(self, text: str) -> Dict[str, any]:
        """Extract all contact information from text."""
        return {
            "emails": self.extract_emails(text),
            "urls": self.extract_urls(text),
            "domains": self.extract_domains(text),
            "company": self.extract_company(text),
            "social_profiles": self.extract_social_profiles(text),
            "has_contact_info": self.has_contact_info(text)
        }
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses."""
        if not text:
            return []
        
        emails = self.EMAIL_PATTERN.findall(text)
        return list(set(emails))
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs."""
        if not text:
            return []
        
        urls = self.URL_PATTERN.findall(text)
        return list(set(urls))
    
    def extract_domains(self, text: str) -> List[str]:
        """Extract domain names."""
        if not text:
            return []
        
        domains = set()
        
        # From URLs
        urls = self.extract_urls(text)
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domains.add(parsed.netloc)
            except Exception:
                pass
        
        # Standalone domains
        standalone = self.DOMAIN_PATTERN.findall(text)
        domains.update(standalone)
        
        # Filter common sites
        filtered = [
            d for d in domains
            if not any(x in d.lower() for x in [
                'reddit.com', 'imgur.com', 'youtube.com', 
                'twitter.com', 'facebook.com', 'linkedin.com'
            ])
        ]
        
        return list(filtered)
    
    def extract_company(self, text: str) -> Optional[str]:
        """Extract company name."""
        if not text:
            return None
        
        for pattern in self.COMPANY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                company = match.group(1).strip()
                if 2 < len(company) < 50:
                    company = company.rstrip('.,;:')
                    return company
        
        return None
    
    def has_contact_info(self, text: str) -> bool:
        """Check if text has contact information."""
        if not text:
            return False
        
        has_email = len(self.extract_emails(text)) > 0
        has_domain = len(self.extract_domains(text)) > 0
        
        contact_keywords = [
            'email', 'contact', 'reach out', 'dm me', 
            'message me', 'get in touch', 'reach me'
        ]
        has_keyword = any(kw in text.lower() for kw in contact_keywords)
        
        return has_email or has_domain or has_keyword
    
    def extract_social_profiles(self, text: str) -> Dict[str, List[str]]:
        """Extract social media profile links from text."""
        if not text:
            return {}
        
        profiles = {
            "twitter": [],
            "linkedin": [],
            "github": []
        }
        
        # Extract Twitter/X profiles
        twitter_matches = self.TWITTER_PATTERN.findall(text)
        profiles["twitter"] = list(set([
            f"https://twitter.com/{username}" for username in twitter_matches
        ]))
        
        # Extract LinkedIn profiles from URLs
        urls = self.extract_urls(text)
        for url in urls:
            linkedin_match = self.LINKEDIN_PATTERN.search(url)
            if linkedin_match:
                username = linkedin_match.group(1)
                if "/company/" in url:
                    profiles["linkedin"].append(f"https://linkedin.com/company/{username}")
                else:
                    profiles["linkedin"].append(f"https://linkedin.com/in/{username}")
        
        # Extract LinkedIn from text directly
        linkedin_matches = self.LINKEDIN_PATTERN.findall(text)
        for username in linkedin_matches:
            profile_url = f"https://linkedin.com/in/{username}"
            if profile_url not in profiles["linkedin"]:
                profiles["linkedin"].append(profile_url)
        
        # Extract GitHub profiles
        github_matches = self.GITHUB_PATTERN.findall(text)
        profiles["github"] = list(set([
            f"https://github.com/{username}" for username in github_matches
        ]))
        
        return profiles
    
    def extract_budget_signals(self, text: str) -> Dict[str, any]:
        """Extract budget-related signals."""
        budget_keywords = [
            'budget', 'paid', 'contract', 'rfp', 'proposal',
            'compensation', 'salary', 'rate', 'hourly', 'project'
        ]
        
        has_budget = any(kw in text.lower() for kw in budget_keywords)
        
        # Look for dollar amounts
        dollar_pattern = r'\$[\d,]+(?:\.\d{2})?'
        amounts = re.findall(dollar_pattern, text)
        
        return {
            "has_budget_mention": has_budget,
            "amounts_mentioned": amounts,
            "budget_score": 1.0 if (has_budget or amounts) else 0.0
        }

