"""
Environment variable validator for Rixly.
Validates that all required environment variables are set.
"""

import os
import sys
from typing import Dict, List, Optional, Tuple


# Required environment variables
REQUIRED_ENV_VARS = {
    # Reddit API (required)
    "REDDIT_CLIENT_ID": "Reddit API client ID",
    "REDDIT_CLIENT_SECRET": "Reddit API client secret",
    
    # LLM API (at least one required)
    "GROQ_API_KEY": "Groq API key (or OPENAI_API_KEY)",
    "OPENAI_API_KEY": "OpenAI API key (or GROQ_API_KEY)",
}

# Optional but recommended environment variables
OPTIONAL_ENV_VARS = {
    "API_KEY": "API authentication key (defaults to 'dev_api_key')",
    "REDDIT_USER_AGENT": "Reddit user agent string (defaults to 'rixly/1.0')",
    "DATABASE_URL": "PostgreSQL database URL (or use DATABASE_HOST, DATABASE_USER, etc.)",
    "DATABASE_HOST": "Database host (defaults to 'localhost')",
    "DATABASE_PORT": "Database port (defaults to 5432)",
    "DATABASE_NAME": "Database name (defaults to 'rixly')",
    "DATABASE_USER": "Database user (defaults to 'rixly')",
    "DATABASE_PASSWORD": "Database password (defaults to 'rixly')",
    "LOG_LEVEL": "Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (defaults to 'INFO')",
    "LOG_FILE": "Log file path (defaults to 'logs/app.log')",
    "ENVIRONMENT": "Environment: development or production (defaults to 'development')",
    "SCHEDULER_ENABLED": "Enable built-in scheduler in API service (defaults to 'false' - use separate scheduler service with --profile scheduler)",
    "SCHEDULER_CHECK_INTERVAL": "Scheduler check interval in seconds (defaults to 60)",
    "JOB_COOLDOWN_MINUTES": "Job cooldown in minutes (defaults to 5)",
    "REDDIT_RATE_LIMIT_DELAY": "Reddit rate limit delay in seconds (defaults to 1.0)",
    "REDDIT_MAX_REQUESTS_PER_MINUTE": "Max Reddit requests per minute (defaults to 60)",
    "REDDIT_CONNECTION_TIMEOUT": "Reddit connection timeout in seconds (defaults to 30.0)",
    "REDDIT_RETRY_ATTEMPTS": "Number of retry attempts for transient failures (defaults to 3)",
    "REDDIT_RETRY_DELAY": "Initial retry delay in seconds, exponential backoff (defaults to 2.0)",
    "REDDIT_MAX_POSTS_PER_SEARCH": "Max posts per search (defaults to 1000)",
    "REDDIT_MAX_COMMENTS_PER_POST": "Max comments per post (defaults to 500)",
    "VPN_ENABLED": "Enable VPN for scraping (defaults to 'false')",
    "VPN_CONFIG_PATH": "Path to WireGuard VPN config file (required if VPN_ENABLED=true)",
}


class EnvValidationError(Exception):
    """Raised when environment validation fails."""
    pass


def validate_required_env() -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        Tuple of (is_valid, list_of_missing_vars)
    """
    missing = []
    
    # Check Reddit credentials
    if not os.getenv("REDDIT_CLIENT_ID"):
        missing.append("REDDIT_CLIENT_ID")
    if not os.getenv("REDDIT_CLIENT_SECRET"):
        missing.append("REDDIT_CLIENT_SECRET")
    
    # Check LLM API keys (at least one required)
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not groq_key and not openai_key:
        missing.append("GROQ_API_KEY or OPENAI_API_KEY (at least one required)")
    
    is_valid = len(missing) == 0
    return is_valid, missing


def validate_database_config() -> Tuple[bool, List[str]]:
    """
    Validate database configuration.
    Either DATABASE_URL or all database parts must be set.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # DATABASE_URL is set, validate format
        if not database_url.startswith(("postgresql://", "postgres://")):
            issues.append("DATABASE_URL must start with 'postgresql://' or 'postgres://'")
    else:
        # Check individual parts (they have defaults, so this is just informational)
        pass  # All have defaults, so no validation needed
    
    is_valid = len(issues) == 0
    return is_valid, issues


def validate_all() -> Tuple[bool, List[str]]:
    """
    Validate all environment variables.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    all_issues = []
    
    # Validate required vars
    req_valid, req_missing = validate_required_env()
    if not req_valid:
        all_issues.extend(req_missing)
    
    # Validate database config
    db_valid, db_issues = validate_database_config()
    if not db_valid:
        all_issues.extend(db_issues)
    
    is_valid = len(all_issues) == 0
    return is_valid, all_issues


def print_validation_report(verbose: bool = False) -> None:
    """
    Print a validation report of environment variables.
    
    Args:
        verbose: If True, show all variables (including optional)
    """
    print("=" * 60)
    print("Rixly Environment Variable Validation")
    print("=" * 60)
    print()
    
    # Required variables
    print("Required Variables:")
    print("-" * 60)
    req_valid, req_missing = validate_required_env()
    
    for var, description in REQUIRED_ENV_VARS.items():
        value = os.getenv(var)
        if var == "GROQ_API_KEY" or var == "OPENAI_API_KEY":
            # Special handling for LLM keys (at least one required)
            if req_valid or (var == "GROQ_API_KEY" and os.getenv("OPENAI_API_KEY")) or (var == "OPENAI_API_KEY" and os.getenv("GROQ_API_KEY")):
                status = "✓ SET" if value else "⚠ OPTIONAL (other LLM key set)"
            else:
                status = "✗ MISSING" if not value else "✓ SET"
        else:
            status = "✓ SET" if value else "✗ MISSING"
        
        print(f"  {status:12} {var:30} - {description}")
        if value and verbose:
            # Show masked value
            masked = "***MASKED***" if len(value) > 8 else value
            print(f"              Value: {masked}")
    
    print()
    
    # Database validation
    print("Database Configuration:")
    print("-" * 60)
    db_valid, db_issues = validate_database_config()
    
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"  ✓ SET      DATABASE_URL - Using full database URL")
        if verbose:
            # Mask password in URL
            import re
            masked_url = re.sub(r'(://[^:]+:)([^@]+)(@)', r'\1***MASKED***\3', database_url)
            print(f"              Value: {masked_url}")
    else:
        print(f"  ⚠ USING    DATABASE_URL - Using individual parts (with defaults)")
        if verbose:
            print(f"              DATABASE_HOST: {os.getenv('DATABASE_HOST', 'localhost')}")
            print(f"              DATABASE_PORT: {os.getenv('DATABASE_PORT', '5432')}")
            print(f"              DATABASE_NAME: {os.getenv('DATABASE_NAME', 'rixly')}")
            print(f"              DATABASE_USER: {os.getenv('DATABASE_USER', 'rixly')}")
            print(f"              DATABASE_PASSWORD: ***MASKED***")
    
    print()
    
    # Optional variables (if verbose)
    if verbose:
        print("Optional Variables:")
        print("-" * 60)
        for var, description in OPTIONAL_ENV_VARS.items():
            value = os.getenv(var)
            status = "✓ SET" if value else "○ NOT SET (using default)"
            print(f"  {status:12} {var:30} - {description}")
            if value and var in ["API_KEY", "DATABASE_PASSWORD"]:
                masked = "***MASKED***" if len(value) > 8 else value
                print(f"              Value: {masked}")
        print()
    
    # Summary
    print("Validation Summary:")
    print("-" * 60)
    is_valid, issues = validate_all()
    
    if is_valid:
        print("  ✓ All required environment variables are set!")
    else:
        print("  ✗ Missing required environment variables:")
        for issue in issues:
            print(f"    - {issue}")
        print()
        print("  Please set the missing variables in your .env file or environment.")
    
    print("=" * 60)


def validate_and_exit(exit_on_error: bool = True) -> bool:
    """
    Validate environment and optionally exit on error.
    
    Args:
        exit_on_error: If True, exit with code 1 on validation failure
        
    Returns:
        True if valid, False otherwise
    """
    is_valid, issues = validate_all()
    
    if not is_valid:
        print("\n❌ Environment validation failed!")
        print("\nMissing or invalid environment variables:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease check your .env file or environment variables.")
        print("Run 'python scripts/validate_env.py' for a detailed report.")
        
        if exit_on_error:
            sys.exit(1)
    
    return is_valid


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Rixly environment variables")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show all variables including optional ones"
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Exit with code 1 if validation fails"
    )
    
    args = parser.parse_args()
    
    print_validation_report(verbose=args.verbose)
    
    if args.exit_on_error:
        is_valid, _ = validate_all()
        if not is_valid:
            sys.exit(1)

