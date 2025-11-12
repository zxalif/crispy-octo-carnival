"""
Database models using SQLAlchemy.
Simplified for Rixly - KeywordSearch + Lead only.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, 
    String, Text, JSON, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class KeywordSearch(Base):
    """Keyword search configuration."""
    
    __tablename__ = "keyword_searches"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    keywords = Column(JSON, nullable=False)  # List of keywords
    patterns = Column(JSON, nullable=False)  # List of patterns
    platforms = Column(JSON, nullable=False)  # ["reddit"] - future: ["reddit", "linkedin", "twitter"]
    
    # Platform-specific configs (JSON)
    reddit_config = Column(JSON, nullable=True)  # {subreddits: [], limit: 100, include_comments: true, sort: "new"}
    linkedin_config = Column(JSON, nullable=True)  # Future: {groups: [], limit: 50}
    twitter_config = Column(JSON, nullable=True)  # Future: {hashtags: [], limit: 100}
    
    # Scraping settings
    scraping_mode = Column(String(20), default="scheduled")  # "scheduled" or "one_time"
    scraping_interval = Column(String(10), nullable=True)  # "30m", "1h", "6h", "24h" (only for scheduled)
    enabled = Column(Boolean, default=True)
    
    # Webhook (optional)
    webhook_url = Column(String(500), nullable=True)  # Optional webhook URL for notifications
    
    # Tracking
    last_scrape_at = Column(DateTime, nullable=True)
    next_scrape_at = Column(DateTime, nullable=True)
    
    # Job tracking
    scraping_status = Column(String(20), nullable=True)  # "running", "completed", "failed", None
    scraping_started_at = Column(DateTime, nullable=True)
    scraping_completed_at = Column(DateTime, nullable=True)
    scraping_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    leads = relationship("Lead", back_populates="keyword_search", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_keyword_search_enabled', 'enabled'),
        Index('idx_keyword_search_next_scrape', 'next_scrape_at'),
        Index('idx_keyword_search_mode', 'scraping_mode'),
        Index('idx_keyword_search_status', 'scraping_status'),
    )


class ScrapedContent(Base):
    """Tracks scraped content to prevent duplicate processing."""
    
    __tablename__ = "scraped_content"
    
    id = Column(String(50), primary_key=True)
    keyword_search_id = Column(String(50), ForeignKey('keyword_searches.id'), nullable=False)
    
    # Source identification
    source = Column(String(50), nullable=False)  # "reddit", "linkedin", "twitter"
    source_id = Column(String(100), nullable=False)  # Post/comment ID
    url = Column(String(500), nullable=False)  # Full URL
    
    # Processing info
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_lead = Column(Boolean, default=False)  # Whether a lead was created from this
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    keyword_search = relationship("KeywordSearch")
    
    # Indexes - critical for duplicate checking
    __table_args__ = (
        Index('idx_scraped_content_search_source', 'keyword_search_id', 'source', 'source_id', unique=True),
        Index('idx_scraped_content_url', 'url'),
        Index('idx_scraped_content_processed', 'processed_at'),
    )


class LLMCache(Base):
    """Cache for LLM analysis results to prevent duplicate API calls."""
    
    __tablename__ = "llm_cache"
    
    id = Column(String(50), primary_key=True)
    
    # Cache key: hash of text content + cache type
    cache_key = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 hash
    cache_type = Column(String(50), nullable=False)  # "classification" or "info_extraction"
    
    # Original text (for debugging/verification, truncated to 1000 chars)
    text_preview = Column(String(1000), nullable=True)
    
    # Cached result (JSON)
    result = Column(JSON, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    use_count = Column(Float, default=1.0)  # Track how many times cache was hit
    
    # Indexes
    __table_args__ = (
        Index('idx_llm_cache_key', 'cache_key', unique=True),
        Index('idx_llm_cache_type', 'cache_type'),
        Index('idx_llm_cache_last_used', 'last_used_at'),
    )


class Lead(Base):
    """Lead/opportunity record (platform-agnostic)."""
    
    __tablename__ = "leads"
    
    id = Column(String(50), primary_key=True)
    keyword_search_id = Column(String(50), ForeignKey('keyword_searches.id'), nullable=False)
    
    # Source information (platform-agnostic)
    source = Column(String(50), nullable=False)  # "reddit", "linkedin", "twitter"
    source_type = Column(String(20), nullable=False)  # "post", "comment", "tweet", "reply"
    source_id = Column(String(100), nullable=False)
    parent_post_id = Column(String(100), nullable=True)  # For comments/replies
    
    # Content
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    
    # Matched information
    matched_keywords = Column(JSON, nullable=False)
    detected_pattern = Column(String(200), nullable=True)
    
    # Extracted contact information
    domain = Column(String(200), nullable=True)
    company = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    author_profile_url = Column(String(500), nullable=True)
    social_profiles = Column(JSON, nullable=True)  # Twitter, LinkedIn, GitHub profiles
    
    # Classification
    opportunity_type = Column(String(50), nullable=True)
    opportunity_subtype = Column(String(100), nullable=True)
    
    # Scores
    relevance_score = Column(Float, default=0.0)
    urgency_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    
    # Additional data
    extracted_info = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(20), default="new")  # new, qualified, contacted, converted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    keyword_search = relationship("KeywordSearch", back_populates="leads")
    
    # Indexes
    __table_args__ = (
        Index('idx_lead_search_id', 'keyword_search_id'),
        Index('idx_lead_source', 'source', 'source_type'),
        Index('idx_lead_source_id', 'source_id', 'keyword_search_id'),  # For duplicate detection
        Index('idx_lead_status', 'status'),
        Index('idx_lead_score', 'total_score'),
        Index('idx_lead_opportunity_type', 'opportunity_type'),
        Index('idx_lead_created', 'created_at'),
        Index('idx_lead_url', 'url'),  # For URL-based duplicate checking
    )
