"""
Opportunity classifier using LLM.
"""

import json
from typing import Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import get_logger
from core.llm_provider import get_llm
from modules.analyzer.llm_cache import generate_cache_key
from modules.database.storage import LeadStorage

logger = get_logger(__name__)


class OpportunityClassifier:
    """Classifies opportunities using LLM."""
    
    SYSTEM_PROMPT = """You are an AI that classifies business opportunities and leads from social media posts and comments.

CRITICAL: A LEAD is when someone is LOOKING TO HIRE/BUY/PARTNER/COLLABORATE. A LEAD is NOT when someone is OFFERING their services.

IS A LEAD (is_lead: true) - ANY business opportunity where someone needs something:
- Hiring/Freelancing: "I need a designer", "Looking for a developer", "Want to hire", "Need someone to build X"
- Consulting: "Need advice on X", "Looking for an expert in Y", "Who can help me with Z"
- Security: "Need security audit", "Looking for penetration testing", "Need vulnerability assessment"
- Sales: "Looking to buy X", "Need a service provider for Y", "Want to purchase Z"
- Marketing: "Looking for content partnership", "Need sponsorship", "Want to collaborate on campaign"
- Partnership: "Looking for business partner", "Need co-founder", "Want to partner on project"
- Investment: "Looking for investors", "Need funding", "Seeking capital"
- Other opportunities: Any situation where someone is seeking something (product, service, partnership, advice, etc.)

IS NOT A LEAD (is_lead: false):
- Someone OFFERING their services (e.g., "I'm a designer", "I provide X services", "Hire me", "Available for work")
- Someone advertising their portfolio/services (e.g., "Check out my portfolio", "I do logo design", "Rates: $X")
- Service providers looking for clients (e.g., "I'm available for projects", "Looking for clients", "Contact me for...")
- Job seekers looking for work
- General discussions without a clear need/request

Your task is to analyze text and determine:
1. Is this a genuine opportunity/lead? (true if someone wants to HIRE/BUY/PARTNER/COLLABORATE, false if they're OFFERING services)
2. What type of opportunity? (hiring, consulting, security, sales, marketing, partnership, investment, other)
3. What is the specific need/subtype? (e.g., "react_developer", "security_audit", "financial_expert", "saas_tool", "content_partnership")

Opportunity Types (only if is_lead: true):
- hiring: Looking to hire someone for a job/project/freelance work
- consulting: Need expert consultation, advice, or guidance
- security: Security audit, penetration testing, vulnerability assessment, security consulting
- sales: Looking for a product/service to buy or subscribe to
- marketing: Content partnership, sponsorship, collaboration, influencer marketing
- partnership: Business partnership, co-founder, joint venture
- investment: Seeking investors, funding, capital
- other: Any other business opportunity that doesn't fit above categories (still valid!)

Return JSON only, no explanation:
{
  "is_lead": true/false,
  "opportunity_type": "type" (or null if is_lead: false),
  "opportunity_subtype": "specific_need" (or null if is_lead: false),
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of why this is/is not a lead"
}"""
    
    def __init__(self, storage: Optional[LeadStorage] = None):
        """
        Initialize classifier.
        
        Args:
            storage: Optional LeadStorage instance for caching
        """
        self.llm = get_llm()
        self.storage = storage
        logger.info("Initialized OpportunityClassifier", has_cache=storage is not None)
    
    def classify(
        self,
        text: str,
        matched_keywords: list[str],
        detected_pattern: Optional[str] = None
    ) -> Dict:
        """
        Classify an opportunity.
        
        Uses LLM cache if storage is available to prevent duplicate API calls.
        
        Args:
            text: Text to classify
            matched_keywords: Keywords that matched
            detected_pattern: Pattern that was detected
            
        Returns:
            Classification result dictionary
        """
        # Check cache first
        if self.storage:
            cache_key = generate_cache_key(text, "classification")
            cached_result = self.storage.get_llm_cache(cache_key, "classification")
            if cached_result:
                logger.debug("Using cached classification result")
                return cached_result
        
        try:
            # Build user message with context
            service_provider_indicators = [
                "i'm a", "i am a", "i provide", "i offer", "i do", "i specialize",
                "portfolio", "rates:", "pricing:", "contact:", "hire me", "available for",
                "looking for clients", "seeking clients", "need clients", "want clients",
                "years of experience", "my services", "my work", "check out my"
            ]
            
            has_service_provider_language = any(
                indicator.lower() in text.lower() for indicator in service_provider_indicators
            )
            
            context_note = ""
            if has_service_provider_language:
                context_note = "\n⚠️ WARNING: This text contains language typical of service providers (e.g., 'I'm a', 'portfolio', 'rates', 'contact me'). This is likely NOT a lead - it's someone OFFERING services, not looking to HIRE."
            
            user_message = f"""Text: {text}

Matched Keywords: {', '.join(matched_keywords)}
Detected Pattern: {detected_pattern or 'N/A'}{context_note}

Analyze this text carefully. Is the person LOOKING TO HIRE/BUY services, or are they OFFERING their services?

Classify this opportunity."""
            
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
            
            logger.debug(
                "Classified opportunity",
                is_lead=result.get("is_lead"),
                type=result.get("opportunity_type"),
                subtype=result.get("opportunity_subtype")
            )
            
            # Store in cache
            if self.storage:
                cache_key = generate_cache_key(text, "classification")
                try:
                    self.storage.set_llm_cache(
                        cache_key=cache_key,
                        cache_type="classification",
                        result=result,
                        text_preview=text[:1000]
                    )
                except Exception as e:
                    # Log but don't fail - caching is best effort
                    logger.warning("Failed to cache classification result", error=str(e))
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response", error=str(e), content=content)
            return {
                "is_lead": False,
                "opportunity_type": "unknown",
                "opportunity_subtype": "unknown",
                "confidence": 0.0,
                "reasoning": "Failed to parse response"
            }
        except Exception as e:
            logger.error("Classification failed", error=str(e))
            return {
                "is_lead": False,
                "opportunity_type": "error",
                "opportunity_subtype": "error",
                "confidence": 0.0,
                "reasoning": str(e)
            }
    
    def is_valid_lead(self, classification: Dict) -> bool:
        """
        Check if classification indicates a valid lead.
        
        Args:
            classification: Classification result
            
        Returns:
            True if valid lead (including "other" type - all opportunities are valid)
        """
        return (
            classification.get("is_lead", False) and
            classification.get("confidence", 0.0) > 0.5 and
            classification.get("opportunity_type") not in ["unknown", "error"]
        )

