"""
Structured information extractor using LLM.
Extracts budget, timeline, requirements, and skills from opportunity text.
"""

import json
from typing import Dict, Optional, Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import get_logger
from core.llm_provider import get_llm

logger = get_logger(__name__)


class InfoExtractor:
    """Extracts structured information (budget, timeline, requirements) using LLM."""
    
    SYSTEM_PROMPT = """You are an expert at extracting structured information from business opportunity posts.

Your task is to extract:
1. **Budget**: Payment amount, compensation, or budget range
2. **Timeline**: Project duration, deadline, or time frame
3. **Requirements**: Skills, experience, or qualifications needed
4. **Location**: Remote, on-site, or specific location

CRITICAL RULES FOR BUDGET EXTRACTION:
- Extract the FULL budget range if mentioned (e.g., "$1K–$1.5K" → min: 1000, max: 1500)
- Handle various formats: "$1,000-$1,500", "$1K-$1.5K", "$20–$25/hr", "Avg weekly: $1K–$1.5K"
- For hourly rates, convert to project budget if possible (e.g., "$20–$25/hr" for 40 hours/week → $800–$1000/week)
- Extract single amounts if no range (e.g., "$500" → budget: 500)
- Handle abbreviations: K = thousands, M = millions (e.g., "$1K" = 1000, "$1.5K" = 1500, "$1K–$1.5K" = min: 1000, max: 1500)
- ALWAYS return numbers WITHOUT currency symbols (e.g., 1000 not "$1000", 1500 not "$1.5K")
- For ranges like "$1K–$1.5K", extract BOTH min and max as separate numbers: budget_min: 1000, budget_max: 1500
- NEVER include dollar signs, commas, or currency symbols in the numeric values
- If multiple budget mentions, extract the most relevant one (usually the main compensation)
- Ensure budget_min and budget_max are both numbers (not strings) when a range is detected

Return JSON only, no explanation:
{
  "budget": number or null,  // Single budget amount (if no range)
  "budget_min": number or null,  // Minimum budget (for ranges)
  "budget_max": number or null,  // Maximum budget (for ranges)
  "budget_currency": "USD" or "EUR" or "GBP" or null,  // Currency code
  "budget_type": "fixed" or "hourly" or "weekly" or "monthly" or "project" or null,
  "timeline": string or null,  // e.g., "2 weeks", "1 month", "ASAP", "flexible"
  "requirements": array of strings or null,  // e.g., ["React", "TypeScript", "5 years experience"]
  "skills": array of strings or null,  // Technical skills needed
  "location": string or null,  // e.g., "Remote", "NYC", "On-site"
  "notes": string or null  // Any additional relevant information
}

Examples:
Input: "Flexible schedule (min 2 days/week). Pickup spot: Jamaica, Queens (6AM-ish). Avg weekly: **$1K–$1.5K**. Breakdown is roughly **$20–$25/hr**"
Output: {
  "budget_min": 1000,
  "budget_max": 1500,
  "budget_currency": "USD",
  "budget_type": "weekly",
  "timeline": "flexible",
  "location": "Jamaica, Queens",
  "notes": "Hourly rate: $20–$25/hr, minimum 2 days/week"
}

Input: "Budget: $1,000–$1,500"
Output: {
  "budget_min": 1000,
  "budget_max": 1500,
  "budget_currency": "USD",
  "budget_type": "project"
}

Input: "$1K–$1.5K per week"
Output: {
  "budget_min": 1000,
  "budget_max": 1500,
  "budget_currency": "USD",
  "budget_type": "weekly"
}

Input: "Looking for a React developer. Budget: $5,000. Need it done in 2 weeks."
Output: {
  "budget": 5000,
  "budget_currency": "USD",
  "budget_type": "project",
  "timeline": "2 weeks",
  "requirements": ["React"],
  "skills": ["React"]
}

Input: "$500 for logo design"
Output: {
  "budget": 500,
  "budget_currency": "USD",
  "budget_type": "project",
  "requirements": ["logo design"]
}"""
    
    def __init__(self):
        """Initialize info extractor."""
        self.llm = get_llm()
        logger.info("Initialized InfoExtractor")
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract structured information from text.
        
        Args:
            text: Opportunity text to analyze
            
        Returns:
            Dictionary with extracted information
        """
        if not text or len(text.strip()) < 10:
            return {}
        
        try:
            user_message = f"""Extract structured information from this opportunity post:

{text}

Extract budget, timeline, requirements, skills, and location. Pay special attention to budget ranges and ensure you extract the FULL range (both min and max)."""
            
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_message)
            ]
            
            # Get LLM response
            response = self.llm.invoke(messages)
            content = response.content
            
            # Parse JSON response
            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    content = parts[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) > 1:
                    content = parts[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Clean and validate budget values - ensure they are numbers, not strings
            if result.get("budget") is not None:
                cleaned = self._clean_budget_value(result["budget"])
                result["budget"] = cleaned if cleaned is not None else result.get("budget")
            if result.get("budget_min") is not None:
                cleaned = self._clean_budget_value(result["budget_min"])
                if cleaned is not None:
                    result["budget_min"] = cleaned
                else:
                    # If cleaning failed, remove invalid value
                    result.pop("budget_min", None)
            if result.get("budget_max") is not None:
                cleaned = self._clean_budget_value(result["budget_max"])
                if cleaned is not None:
                    result["budget_max"] = cleaned
                else:
                    # If cleaning failed, remove invalid value
                    result.pop("budget_max", None)
            
            # Ensure if we have a range, both min and max are present and valid
            if result.get("budget_min") is not None and result.get("budget_max") is None:
                # If only min exists, convert to single budget
                result["budget"] = result["budget_min"]
                result.pop("budget_min", None)
            elif result.get("budget_max") is not None and result.get("budget_min") is None:
                # If only max exists, use as single budget
                result["budget"] = result["budget_max"]
                result.pop("budget_max", None)
            
            logger.debug(
                "Extracted structured info",
                has_budget=bool(result.get("budget") or result.get("budget_min")),
                has_timeline=bool(result.get("timeline")),
                has_requirements=bool(result.get("requirements"))
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response for info extraction", error=str(e), content=content[:200])
            return {}
        except Exception as e:
            logger.error("Info extraction failed", error=str(e))
            return {}
    
    def _clean_budget_value(self, value: Any) -> Optional[float]:
        """Clean and convert budget value to number."""
        if value is None:
            return None
        
        # If already a number, return it
        if isinstance(value, (int, float)):
            # Ensure it's positive and reasonable
            num = float(value)
            if num < 0 or num > 1000000000:  # Sanity check: max 1 billion
                return None
            return num
        
        if isinstance(value, str):
            # Remove all currency symbols, commas, spaces, and other non-numeric chars except K, M, and decimal point
            cleaned = value.strip()
            
            # Remove currency symbols
            cleaned = cleaned.replace('$', '').replace('€', '').replace('£', '').replace(',', '').replace(' ', '')
            
            # Handle K (thousands) and M (millions) - case insensitive
            multiplier = 1
            if cleaned.upper().endswith('K'):
                multiplier = 1000
                cleaned = cleaned[:-1]
            elif cleaned.upper().endswith('M'):
                multiplier = 1000000
                cleaned = cleaned[:-1]
            
            # Remove any remaining non-numeric characters except decimal point
            import re
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            
            # Handle decimal values (e.g., "1.5" for 1.5K = 1500)
            try:
                num = float(cleaned) * multiplier
                # Sanity check
                if num < 0 or num > 1000000000:
                    return None
                return num
            except (ValueError, TypeError):
                return None
        
        return None

