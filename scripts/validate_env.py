#!/usr/bin/env python3
"""
Environment variable validation script for Rixly.
Run this script to validate your .env configuration.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.env_validator import print_validation_report, validate_and_exit


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate Rixly environment variables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_env.py              # Basic validation
  python scripts/validate_env.py -v           # Verbose (show all variables)
  python scripts/validate_env.py --exit-on-error  # Exit with code 1 on failure
        """
    )
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
        validate_and_exit(exit_on_error=True)

