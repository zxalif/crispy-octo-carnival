"""
LLM provider for Rixly.
Supports Groq and OpenAI.
"""

from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from core.config import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class LLMProvider:
    """Manages LLM instances for the application."""
    
    def __init__(self):
        """Initialize LLM provider."""
        self.config = get_config()
        self._groq_client: Optional[BaseChatModel] = None
        self._openai_client: Optional[BaseChatModel] = None
    
    def get_groq_client(
        self,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.0,
        **kwargs
    ) -> BaseChatModel:
        """
        Get Groq LLM client (fast, cheap inference).
        
        Args:
            model: Model name
            temperature: Temperature for generation
            **kwargs: Additional arguments
            
        Returns:
            Groq chat model instance
        """
        if not self.config.groq_api_key:
            logger.warning("Groq API key not configured, falling back to OpenAI")
            return self.get_openai_client(temperature=temperature, **kwargs)
        
        if self._groq_client is None:
            self._groq_client = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=self.config.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                **kwargs
            )
            logger.info("Initialized Groq client", model=model)
        
        return self._groq_client
    
    def get_openai_client(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        **kwargs
    ) -> BaseChatModel:
        """
        Get OpenAI LLM client.
        
        Args:
            model: Model name
            temperature: Temperature for generation
            **kwargs: Additional arguments
            
        Returns:
            OpenAI chat model instance
        """
        if not self.config.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        if self._openai_client is None:
            self._openai_client = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=self.config.openai_api_key,
                **kwargs
            )
            logger.info("Initialized OpenAI client", model=model)
        
        return self._openai_client
    
    def get_default_client(self, **kwargs) -> BaseChatModel:
        """
        Get default LLM client (Groq preferred, OpenAI fallback).
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Default chat model instance
        """
        try:
            return self.get_groq_client(**kwargs)
        except Exception as e:
            logger.warning("Failed to get Groq client, using OpenAI", error=str(e))
            return self.get_openai_client(**kwargs)


# Global LLM provider instance
_llm_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """Get or create global LLM provider instance."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider()
    return _llm_provider


def get_llm(provider: str = "default", **kwargs) -> BaseChatModel:
    """
    Get LLM client.
    
    Args:
        provider: Provider name (default, groq, openai)
        **kwargs: Additional arguments
        
    Returns:
        Chat model instance
    """
    llm_provider = get_llm_provider()
    
    if provider == "groq":
        return llm_provider.get_groq_client(**kwargs)
    elif provider == "openai":
        return llm_provider.get_openai_client(**kwargs)
    else:
        return llm_provider.get_default_client(**kwargs)

