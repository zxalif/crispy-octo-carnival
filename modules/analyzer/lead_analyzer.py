"""
Main lead analyzer that orchestrates classification, extraction, and scoring.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.state import LeadState
from modules.analyzer.classifier import OpportunityClassifier
from modules.analyzer.extractor import ContactExtractor
from modules.analyzer.scorer import LeadScorer
from modules.analyzer.info_extractor import InfoExtractor
from modules.database.storage import LeadStorage

logger = get_logger(__name__)


class LeadAnalyzer:
    """Analyzes leads using LLM and scoring algorithms."""
    
    def __init__(self, storage: Optional[LeadStorage] = None):
        """
        Initialize lead analyzer.
        
        Args:
            storage: Optional LeadStorage instance for LLM caching
        """
        self.storage = storage
        self.classifier = OpportunityClassifier(storage=storage)
        self.extractor = ContactExtractor()
        self.scorer = LeadScorer()
        self.info_extractor = InfoExtractor(storage=storage)
        
        logger.info("Initialized LeadAnalyzer")
    
    def analyze_lead(
        self,
        lead_data: Dict[str, Any],
        total_keywords: int
    ) -> Optional[LeadState]:
        """
        Analyze a single lead.
        
        Args:
            lead_data: Raw lead data
            total_keywords: Total keywords in search
            
        Returns:
            Analyzed LeadState or None if invalid
        """
        # Extract text
        text = lead_data.get("content", "")
        if lead_data.get("title"):
            text = f"{lead_data['title']} {text}"
        
        matched_keywords = lead_data.get("matched_keywords", [])
        detected_pattern = lead_data.get("detected_pattern")
        
        try:
            # Classify opportunity
            classification = self.classifier.classify(
                text=text,
                matched_keywords=matched_keywords,
                detected_pattern=detected_pattern
            )
            
            # Extract contact information
            contact_info = self.extractor.extract(text)
            budget_info = self.extractor.extract_budget_signals(text)
            
            # Extract structured information (budget, timeline, requirements) using LLM
            structured_info = self.info_extractor.extract(text)
            
            # Get social profiles from contact info
            social_profiles = contact_info.get("social_profiles", {})
            
            # Determine if it's a valid lead
            if not self.classifier.is_valid_lead(classification):
                logger.debug(
                    "Filtered out invalid lead",
                    confidence=classification.get("confidence"),
                    type=classification.get("opportunity_type")
                )
                return None
            
            # Score the lead
            scores = self.scorer.score_lead(
                text=text,
                matched_keywords=matched_keywords,
                total_keywords=total_keywords,
                has_urgency=lead_data.get("has_urgency", False),
                has_budget=budget_info.get("has_budget_mention", False),
                has_contact=contact_info.get("has_contact_info", False),
                classification_confidence=classification.get("confidence", 0.5)
            )
            
            # Create LeadState
            lead_id = f"lead_{uuid.uuid4().hex[:12]}"
            
            # Safely extract domain and email (handle empty lists)
            domains = contact_info.get("domains", [])
            emails = contact_info.get("emails", [])
            
            lead = LeadState(
                id=lead_id,
                keyword_search_id=lead_data.get("keyword_search_id", ""),
                matched_keywords=matched_keywords,
                detected_pattern=detected_pattern or "",
                source=lead_data.get("source", "reddit"),
                source_type=lead_data.get("source_type", "post"),
                source_id=lead_data.get("source_id", ""),
                title=lead_data.get("title"),
                content=lead_data.get("content", ""),
                author=lead_data.get("author", ""),
                url=lead_data.get("url", ""),
                domain=domains[0] if domains else None,
                company=contact_info.get("company"),
                email=emails[0] if emails else None,
                author_profile_url=lead_data.get("author_profile_url"),
                social_profiles=social_profiles if social_profiles else None,
                opportunity_type=classification.get("opportunity_type"),
                opportunity_subtype=classification.get("opportunity_subtype"),
                relevance_score=scores["relevance_score"],
                urgency_score=scores["urgency_score"],
                total_score=scores["total_score"],
                extracted_info={
                    "classification": classification,
                    "contact_info": contact_info,
                    "budget_info": budget_info,
                    "scores": scores,
                    # Add structured information (budget, timeline, requirements)
                    "budget": structured_info.get("budget"),
                    "budget_min": structured_info.get("budget_min"),
                    "budget_max": structured_info.get("budget_max"),
                    "budget_currency": structured_info.get("budget_currency", "USD"),
                    "budget_type": structured_info.get("budget_type"),
                    "timeline": structured_info.get("timeline"),
                    "requirements": structured_info.get("requirements"),
                    "skills": structured_info.get("skills"),
                    "location": structured_info.get("location"),
                    "notes": structured_info.get("notes")
                },
                created_at=lead_data.get("created_utc", datetime.utcnow()),
                updated_at=datetime.utcnow(),
                status="new",
                parent_post_id=lead_data.get("parent_post_id")
            )
            
            logger.info(
                "Analyzed lead",
                lead_id=lead_id,
                type=lead.opportunity_type,
                subtype=lead.opportunity_subtype,
                score=lead.total_score
            )
            
            return lead
            
        except Exception as e:
            logger.error("Failed to analyze lead", error=str(e))
            return None
    
    def analyze_leads(
        self,
        leads_data: List[Dict[str, Any]],
        total_keywords: int
    ) -> List[LeadState]:
        """
        Analyze multiple leads.
        
        Args:
            leads_data: List of raw lead data
            total_keywords: Total keywords in search
            
        Returns:
            List of analyzed LeadStates
        """
        analyzed_leads = []
        
        for lead_data in leads_data:
            lead = self.analyze_lead(lead_data, total_keywords)
            if lead:
                analyzed_leads.append(lead)
        
        logger.info(
            "Analyzed leads batch",
            total=len(leads_data),
            valid=len(analyzed_leads)
        )
        
        return analyzed_leads
    
    def filter_by_score(
        self,
        leads: List[LeadState],
        min_score: float = 0.5
    ) -> List[LeadState]:
        """
        Filter leads by minimum score.
        
        Args:
            leads: List of leads
            min_score: Minimum score threshold
            
        Returns:
            Filtered leads
        """
        filtered = [lead for lead in leads if lead.total_score >= min_score]
        
        logger.info(
            "Filtered leads by score",
            total=len(leads),
            filtered=len(filtered),
            min_score=min_score
        )
        
        return filtered
    
    def sort_by_score(self, leads: List[LeadState]) -> List[LeadState]:
        """
        Sort leads by total score (descending).
        
        Args:
            leads: List of leads
            
        Returns:
            Sorted leads
        """
        return sorted(leads, key=lambda x: x.total_score, reverse=True)

