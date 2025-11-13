"""
Configuration management for Rixly.
Simplified - Reddit + LLM only.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Configuration
    api_key: str = Field(default="dev_api_key")
    
    # Reddit API
    reddit_client_id: str = Field(default="")
    reddit_client_secret: str = Field(default="")
    reddit_user_agent: str = Field(default="rixly/1.0")
    
    # LLM API Keys
    groq_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    
    # Database
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL database URL (if not provided, will be built from parts below)"
    )
    database_host: str = Field(default="localhost", description="Database host")
    database_port: int = Field(default=5432, description="Database port")
    database_name: str = Field(default="rixly", description="Database name")
    database_user: str = Field(default="rixly", description="Database user")
    database_password: str = Field(default="rixly", description="Database password")
    
    @property
    def database_url_from_parts(self) -> str:
        """Build database URL from parts."""
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"
    
    # Application Settings
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default="logs/app.log")
    environment: str = Field(default="development")
    
    # Scheduler
    scheduler_enabled: bool = Field(default=True)
    scheduler_check_interval: int = Field(default=60)  # seconds
    
    # Job tracking
    job_cooldown_minutes: int = Field(default=5, description="Minimum minutes between scrapes for same search")
    
    # Reddit Rate Limiting
    reddit_rate_limit_delay: float = Field(
        default=1.0,
        description="Seconds between Reddit API requests (per scraper instance)"
    )
    reddit_max_requests_per_minute: int = Field(
        default=60,
        description="Maximum Reddit API requests per minute (global limit)"
    )
    
    # Reddit Connection Settings
    reddit_connection_timeout: float = Field(
        default=30.0,
        description="Connection timeout in seconds for Reddit API requests"
    )
    reddit_retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for transient failures"
    )
    reddit_retry_delay: float = Field(
        default=2.0,
        description="Initial delay in seconds between retry attempts (exponential backoff)"
    )
    
    # Search Limits (prevent accidental large scrapes)
    reddit_max_posts_per_search: int = Field(
        default=1000,
        description="Maximum posts per search (across all subreddits)"
    )
    reddit_max_comments_per_post: int = Field(
        default=500,
        description="Maximum comments per post"
    )
    
    # VPN Configuration (Optional - for Reddit/Craigslist scraping)
    vpn_enabled: bool = Field(
        default=False,
        description="Enable VPN for scraping (requires WireGuard and VPN config)"
    )
    vpn_config_path: Optional[str] = Field(
        default=None,
        description="Path to WireGuard VPN config file (e.g., /path/to/zola-vpn-client.conf)"
    )
    
    # Redis Configuration (Optional - for rate limiting and caching)
    redis_host: str = Field(
        default="localhost",
        description="Redis host (defaults to 'localhost' for host network mode or local dev)"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port"
    )
    redis_db: int = Field(
        default=0,
        description="Redis database number"
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password (optional)"
    )
    
    # Webhook Configuration
    webhook_secret: Optional[str] = Field(
        default=None,
        description="Secret key for signing webhook requests (HMAC-SHA256). Should match RIXLY_WEBHOOK_SECRET in lead-api."
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Validate that required fields are set."""
        # Check Reddit credentials
        if not self.reddit_client_id or not self.reddit_client_secret:
            raise ValueError(
                "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are required. "
                "Set them in your .env file or environment variables."
            )
        
        # Check LLM API keys (at least one required)
        if not self.groq_api_key and not self.openai_api_key:
            raise ValueError(
                "At least one LLM API key is required. "
                "Set either GROQ_API_KEY or OPENAI_API_KEY in your .env file or environment variables."
            )
        
        return self
    
    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        path = Path("data")
        path.mkdir(exist_ok=True)
        return path


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config

