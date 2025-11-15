"""
Webhook notification sender.
Sends HTTP POST requests to configured webhook URLs with signature verification.
"""

import asyncio
from typing import Dict, Any, Optional
import json
import hmac
import hashlib

import httpx

from core.logger import get_logger
from core.config import get_config

logger = get_logger(__name__)


class WebhookSender:
    """Sends webhook notifications."""
    
    def __init__(self, timeout: int = 10):
        """
        Initialize webhook sender.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def send_lead_created(
        self,
        webhook_url: str,
        lead_data: Dict[str, Any],
        keyword_search_id: str,
        keyword_search_name: str
    ) -> bool:
        """
        Send webhook notification when a lead is created.
        
        Args:
            webhook_url: Webhook URL to send to
            lead_data: Lead data dictionary
            keyword_search_id: Keyword search ID
            keyword_search_name: Keyword search name
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "event": "lead.created",
            "timestamp": lead_data.get("created_at"),
            "keyword_search": {
                "id": keyword_search_id,
                "name": keyword_search_name
            },
            "lead": {
                "id": lead_data.get("id"),
                "title": lead_data.get("title"),
                "url": lead_data.get("url"),
                "author": lead_data.get("author"),
                "opportunity_type": lead_data.get("opportunity_type"),
                "opportunity_subtype": lead_data.get("opportunity_subtype"),
                "total_score": lead_data.get("total_score"),
                "status": lead_data.get("status"),
                "source": lead_data.get("source"),
                "source_type": lead_data.get("source_type")
            }
        }
        
        return await self._send(webhook_url, payload)
    
    async def send_job_completed(
        self,
        webhook_url: str,
        keyword_search_id: str,
        keyword_search_name: str,
        stats: Dict[str, Any]
    ) -> bool:
        """
        Send webhook notification when a scraping job completes.
        
        Args:
            webhook_url: Webhook URL to send to
            keyword_search_id: Keyword search ID
            keyword_search_name: Keyword search name
            stats: Job statistics (leads_created, posts_scraped, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "event": "job.completed",
            "timestamp": stats.get("completed_at"),
            "keyword_search": {
                "id": keyword_search_id,
                "name": keyword_search_name
            },
            "stats": {
                "leads_created": stats.get("leads_created", 0),
                "posts_scraped": stats.get("posts_scraped", 0),
                "comments_scraped": stats.get("comments_scraped", 0),
                "processing_time_seconds": stats.get("processing_time_seconds", 0)
            }
        }
        
        return await self._send(webhook_url, payload)
    
    async def send_job_failed(
        self,
        webhook_url: str,
        keyword_search_id: str,
        keyword_search_name: str,
        error: str
    ) -> bool:
        """
        Send webhook notification when a scraping job fails.
        
        Args:
            webhook_url: Webhook URL to send to
            keyword_search_id: Keyword search ID
            keyword_search_name: Keyword search name
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "event": "job.failed",
            "timestamp": None,  # Will be set by receiver
            "keyword_search": {
                "id": keyword_search_id,
                "name": keyword_search_name
            },
            "error": error
        }
        
        return await self._send(webhook_url, payload)
    
    async def _send(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """
        Send webhook request with optional signature.
        
        Args:
            webhook_url: Webhook URL
            payload: Payload to send
            
        Returns:
            True if successful, False otherwise
        """
        # Extract event type early for logging (avoid conflicts with structlog's 'event' parameter)
        webhook_event_type = payload.get("event")
        
        try:
            # Serialize payload to JSON bytes for signature calculation
            payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            payload_bytes = payload_json.encode('utf-8')
            
            # Build headers
            headers = {"Content-Type": "application/json"}
            
            # Add signature if webhook secret is configured
            config = get_config()
            if config.webhook_secret:
                signature = hmac.new(
                    config.webhook_secret.encode('utf-8'),
                    payload_bytes,
                    hashlib.sha256
                ).hexdigest()
                headers["X-Rixly-Signature"] = signature
                logger.debug("Webhook signature generated", webhook_event=webhook_event_type)
            else:
                logger.debug("Webhook secret not configured - sending without signature", webhook_event=webhook_event_type)
            
            # Send webhook request
            response = await self.client.post(
                webhook_url,
                content=payload_bytes,  # Send raw bytes to ensure signature matches
                headers=headers
            )
            response.raise_for_status()
            
            logger.info("Webhook sent successfully", url=webhook_url, webhook_event=webhook_event_type)
            return True
            
        except httpx.HTTPError as e:
            logger.warning("Webhook request failed", url=webhook_url, error=str(e), webhook_event=webhook_event_type)
            return False
        except Exception as e:
            logger.error("Unexpected error sending webhook", url=webhook_url, error=str(e), webhook_event=webhook_event_type)
            return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global webhook sender instance
_webhook_sender: Optional[WebhookSender] = None


def get_webhook_sender() -> WebhookSender:
    """Get or create global webhook sender instance."""
    global _webhook_sender
    if _webhook_sender is None:
        _webhook_sender = WebhookSender()
    return _webhook_sender

