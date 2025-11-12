"""
Pydantic schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Keyword Search Schemas

class KeywordSearchCreate(BaseModel):
    """Schema for creating a keyword search."""
    
    name: str = Field(..., description="Search name")
    keywords: List[str] = Field(..., description="Keywords to search for")
    patterns: List[str] = Field(default_factory=list, description="Patterns to detect")
    platforms: List[str] = Field(default=["reddit"], description="Platforms to scrape")
    
    # Reddit config
    reddit_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Reddit-specific configuration. Use empty subreddits array [] to search all of Reddit, or provide specific subreddits like [\"forhire\", \"freelance\"]"
    )
    
    # Scraping settings
    scraping_mode: str = Field(
        default="scheduled",
        description="'scheduled' or 'one_time'"
    )
    scraping_interval: Optional[str] = Field(
        None,
        description="'30m', '1h', '6h', '24h' (only for scheduled mode)"
    )
    enabled: bool = Field(default=True, description="Whether search is enabled")
    webhook_url: Optional[str] = Field(
        None,
        description="Optional webhook URL for notifications (lead.created, job.completed, job.failed)"
    )
    
    @field_validator('scraping_mode')
    @classmethod
    def validate_scraping_mode(cls, v):
        """Validate scraping mode."""
        if v not in ['scheduled', 'one_time']:
            raise ValueError("scraping_mode must be 'scheduled' or 'one_time'")
        return v
    
    @field_validator('scraping_interval')
    @classmethod
    def validate_scraping_interval(cls, v):
        """Validate scraping interval."""
        if v is None:
            return v
        
        # Check if interval format is valid
        valid_intervals = ['30m', '1h', '6h', '24h']
        if v not in valid_intervals:
            raise ValueError(f"scraping_interval must be one of: {', '.join(valid_intervals)}")
        
        return v
    
    @model_validator(mode='after')
    def validate_scraping_config(self):
        """Validate scraping mode and interval combination."""
        if self.scraping_mode == 'scheduled':
            if not self.scraping_interval:
                raise ValueError(
                    "scraping_interval is required when scraping_mode is 'scheduled'. "
                    "Provide one of: '30m', '1h', '6h', '24h'"
                )
        elif self.scraping_mode == 'one_time':
            if self.scraping_interval:
                raise ValueError(
                    "scraping_interval should not be provided when scraping_mode is 'one_time'. "
                    "One-time searches don't use intervals."
                )
        
        return self


class KeywordSearchUpdate(BaseModel):
    """Schema for updating a keyword search."""
    
    name: Optional[str] = None
    keywords: Optional[List[str]] = None
    patterns: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    reddit_config: Optional[Dict[str, Any]] = None
    scraping_mode: Optional[str] = None
    scraping_interval: Optional[str] = None
    enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    
    @field_validator('scraping_mode')
    @classmethod
    def validate_scraping_mode(cls, v):
        """Validate scraping mode."""
        if v is not None and v not in ['scheduled', 'one_time']:
            raise ValueError("scraping_mode must be 'scheduled' or 'one_time'")
        return v
    
    @field_validator('scraping_interval')
    @classmethod
    def validate_scraping_interval(cls, v):
        """Validate scraping interval format."""
        if v is None:
            return v
        
        valid_intervals = ['30m', '1h', '6h', '24h']
        if v not in valid_intervals:
            raise ValueError(f"scraping_interval must be one of: {', '.join(valid_intervals)}")
        
        return v
    
    # Note: Mode/interval combination validation is done in the route handler
    # because we need access to the existing search state


class KeywordSearchResponse(BaseModel):
    """Schema for keyword search response."""
    
    id: str
    name: str
    keywords: List[str]
    patterns: List[str]
    platforms: List[str]
    reddit_config: Optional[Dict[str, Any]] = None
    linkedin_config: Optional[Dict[str, Any]] = None
    twitter_config: Optional[Dict[str, Any]] = None
    scraping_mode: str
    scraping_interval: Optional[str] = None
    enabled: bool
    last_scrape_at: Optional[datetime] = None
    next_scrape_at: Optional[datetime] = None
    scraping_status: Optional[str] = None  # "running", "completed", "failed"
    scraping_started_at: Optional[datetime] = None
    scraping_completed_at: Optional[datetime] = None
    scraping_error: Optional[str] = None
    webhook_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Lead Schemas

class LeadResponse(BaseModel):
    """Schema for lead response."""
    
    id: str
    keyword_search_id: str
    source: str
    source_type: str
    source_id: str
    parent_post_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    author: str
    url: str
    matched_keywords: List[str]
    detected_pattern: Optional[str] = None
    domain: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    author_profile_url: Optional[str] = None
    social_profiles: Optional[Dict[str, List[str]]] = None
    opportunity_type: Optional[str] = None
    opportunity_subtype: Optional[str] = None
    relevance_score: float
    urgency_score: float
    total_score: float
    extracted_info: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    
    status: Optional[str] = Field(
        None,
        description="Status: 'new', 'qualified', 'contacted', 'converted'"
    )


# Scrape Response Schema

class ScrapeResponse(BaseModel):
    """Schema for scrape operation response."""
    
    status: str
    keyword_search_id: str
    platforms_processed: List[str]
    posts_scraped: int
    comments_scraped: int
    posts_filtered: int
    comments_filtered: int
    leads_analyzed: int
    leads_created: int
    processing_time_seconds: float
    next_scrape_at: Optional[str] = None
    leads: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


# Statistics Schema

class StatisticsResponse(BaseModel):
    """Schema for statistics response."""
    
    total_leads: int
    by_status: Dict[str, int]
    by_opportunity_type: Dict[str, int]


# Utility Schemas

class KeywordGenerationRequest(BaseModel):
    """Schema for keyword generation request."""
    
    product_description: str = Field(
        ...,
        description="Product or service description to generate keywords from",
        min_length=10
    )
    max_keywords: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of keywords to generate"
    )


class KeywordGenerationResponse(BaseModel):
    """Schema for keyword generation response."""
    
    keywords: List[str] = Field(..., description="Generated keywords")
    count: int = Field(..., description="Number of keywords generated")


class WebsiteSummaryRequest(BaseModel):
    """Schema for website summary request."""
    
    url: str = Field(..., description="Website URL to summarize")
    max_words: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Maximum number of words in summary"
    )


class WebsiteSummaryResponse(BaseModel):
    """Schema for website summary response."""
    
    url: str = Field(..., description="Website URL")
    summary: str = Field(..., description="Website summary")
    word_count: int = Field(..., description="Number of words in summary")
    title: Optional[str] = Field(None, description="Website title if available")


class SemanticQueriesRequest(BaseModel):
    """Schema for semantic queries generation request."""
    
    url: Optional[str] = Field(
        None,
        description="Website URL to analyze (if provided, will scrape website content)"
    )
    business_description: Optional[str] = Field(
        None,
        description="Business description (required if URL not provided)",
        min_length=10
    )
    max_queries: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of semantic queries to generate"
    )
    query_types: List[str] = Field(
        default=["question", "search_query", "problem_statement"],
        description="Types of queries to generate: question, search_query, problem_statement"
    )
    
    @model_validator(mode='after')
    def validate_input(self):
        """Ensure at least one of url or business_description is provided."""
        if not self.url and not self.business_description:
            raise ValueError(
                "Either 'url' or 'business_description' must be provided. "
                "Provide a website URL to scrape, or a business description to analyze."
            )
        return self


class SemanticQueriesResponse(BaseModel):
    """Schema for semantic queries response."""
    
    queries: List[str] = Field(..., description="Generated semantic queries")
    count: int = Field(..., description="Number of queries generated")
    url: Optional[str] = Field(None, description="Website URL if provided")
    title: Optional[str] = Field(None, description="Website title if URL was provided")


# Pagination Schema

class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether there are more items")
    
    @property
    def page(self) -> int:
        """Calculate current page number (1-based)."""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 1


class PaginatedLeadsResponse(PaginatedResponse):
    """Schema for paginated leads response."""
    
    items: List[LeadResponse] = Field(..., description="List of leads")

