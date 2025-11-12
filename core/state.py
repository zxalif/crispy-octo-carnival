"""
State models for Rixly (simplified, no agent state).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class KeywordSearchState:
    """State for a keyword search."""
    
    id: str
    name: str
    keywords: List[str]
    patterns: List[str]
    platforms: List[str]  # ["reddit"] - future: ["reddit", "linkedin", "twitter"]
    
    # Platform-specific configs
    reddit_config: Optional[Dict[str, Any]] = None
    linkedin_config: Optional[Dict[str, Any]] = None
    twitter_config: Optional[Dict[str, Any]] = None
    
    # Scraping settings
    scraping_mode: str = "scheduled"  # "scheduled" or "one_time"
    scraping_interval: Optional[str] = None  # "30m", "1h", "6h", "24h"
    enabled: bool = True
    
    # Webhook (optional)
    webhook_url: Optional[str] = None  # Optional webhook URL for notifications
    
    # Tracking
    last_scrape_at: Optional[datetime] = None
    next_scrape_at: Optional[datetime] = None
    
    # Job tracking
    scraping_status: Optional[str] = None  # "running", "completed", "failed"
    scraping_started_at: Optional[datetime] = None
    scraping_completed_at: Optional[datetime] = None
    scraping_error: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LeadState:
    """State for a lead (simplified, no agent dependencies)."""
    
    id: str
    keyword_search_id: str
    matched_keywords: List[str]
    detected_pattern: Optional[str]
    source: str  # "reddit", "linkedin", "twitter" (future-proof)
    source_type: str  # "post", "comment", "tweet", "reply"
    source_id: str
    
    # Content (required fields first)
    title: Optional[str] = None
    content: str = ""
    author: str = ""
    url: str = ""
    
    # Optional fields
    parent_post_id: Optional[str] = None  # For comments/replies
    
    # Extracted contact information
    domain: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    author_profile_url: Optional[str] = None
    social_profiles: Optional[Dict[str, List[str]]] = None
    
    # AI Classification
    opportunity_type: Optional[str] = None
    opportunity_subtype: Optional[str] = None
    
    # Scores
    relevance_score: float = 0.0
    urgency_score: float = 0.0
    total_score: float = 0.0
    
    # Additional data
    extracted_info: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Status
    status: str = "new"  # new, qualified, contacted, converted
