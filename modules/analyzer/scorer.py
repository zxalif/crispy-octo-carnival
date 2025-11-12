"""
Lead scoring algorithm.
"""

from typing import Dict, List

from core.logger import get_logger

logger = get_logger(__name__)


class LeadScorer:
    """Scores leads based on multiple factors."""
    
    # Scoring weights
    WEIGHTS = {
        "relevance": 0.4,
        "urgency": 0.3,
        "budget": 0.2,
        "contact": 0.1
    }
    
    def __init__(self):
        """Initialize lead scorer."""
        logger.info("Initialized LeadScorer")
    
    def score_lead(
        self,
        text: str,
        matched_keywords: List[str],
        total_keywords: int,
        has_urgency: bool,
        has_budget: bool,
        has_contact: bool,
        classification_confidence: float = 0.5
    ) -> Dict[str, float]:
        """
        Calculate lead score.
        
        Args:
            text: Lead text
            matched_keywords: Keywords that matched
            total_keywords: Total keywords in search
            has_urgency: Whether urgency detected
            has_budget: Whether budget mentioned
            has_contact: Whether contact info present
            classification_confidence: LLM classification confidence
            
        Returns:
            Dictionary with score breakdown
        """
        # Relevance score (keyword match quality + LLM confidence)
        keyword_match_ratio = len(matched_keywords) / max(total_keywords, 1)
        relevance_score = (keyword_match_ratio * 0.5) + (classification_confidence * 0.5)
        relevance_score = min(1.0, relevance_score)
        
        # Urgency score
        urgency_score = 1.0 if has_urgency else 0.5
        
        # Budget score
        budget_score = 1.0 if has_budget else 0.3
        
        # Contact quality score
        contact_score = 1.0 if has_contact else 0.2
        
        # Calculate total score
        total_score = (
            relevance_score * self.WEIGHTS["relevance"] +
            urgency_score * self.WEIGHTS["urgency"] +
            budget_score * self.WEIGHTS["budget"] +
            contact_score * self.WEIGHTS["contact"]
        )
        
        scores = {
            "relevance_score": round(relevance_score, 3),
            "urgency_score": round(urgency_score, 3),
            "budget_score": round(budget_score, 3),
            "contact_score": round(contact_score, 3),
            "total_score": round(total_score, 3)
        }
        
        logger.debug("Scored lead", **scores)
        
        return scores
    
    def classify_by_score(self, total_score: float) -> str:
        """
        Classify lead by score.
        
        Args:
            total_score: Total lead score
            
        Returns:
            Classification (hot, warm, cold)
        """
        if total_score >= 0.8:
            return "hot"
        elif total_score >= 0.5:
            return "warm"
        else:
            return "cold"

