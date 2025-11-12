"""
Utility endpoints for keyword generation and website summarization.
"""

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import get_logger
from core.llm_provider import get_llm
from api.middleware.auth import verify_api_key
from api.models.schemas import (
    KeywordGenerationRequest,
    KeywordGenerationResponse,
    WebsiteSummaryRequest,
    WebsiteSummaryResponse,
    SemanticQueriesRequest,
    SemanticQueriesResponse
)

router = APIRouter(tags=["utilities"])
logger = get_logger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL by adding protocol if missing.
    
    Args:
        url: URL string (may or may not have protocol)
        
    Returns:
        URL with protocol (https://)
    """
    url = url.strip()
    
    # If URL already has protocol, return as-is
    if url.startswith(("http://", "https://")):
        return url
    
    # Add https:// if missing
    return f"https://{url}"


async def scrape_with_playwright(url: str) -> dict:
    """
    Scrape website content using Playwright (for JavaScript-rendered sites).
    
    Args:
        url: Website URL
        
    Returns:
        Dictionary with title and content
    """
    try:
        from playwright.async_api import async_playwright
        from bs4 import BeautifulSoup
        
        async with async_playwright() as p:
            # Launch browser (headless)
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            try:
                # Create context and page
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()
                
                # Navigate and wait for content to load
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait a bit more for React/JS to render
                await page.wait_for_timeout(2000)
                
                # Get rendered HTML
                html = await page.content()
                
                # Close browser
                await context.close()
                await browser.close()
                
                # Parse HTML
                soup = BeautifulSoup(html, "html.parser")
                
                # Extract title
                title = None
                if soup.title:
                    title = soup.title.get_text().strip()
                elif soup.find("h1"):
                    title = soup.find("h1").get_text().strip()
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Extract main content
                main_content = None
                for tag in ["main", "article", "[role='main']", ".content", "#content"]:
                    element = soup.select_one(tag)
                    if element:
                        main_content = element
                        break
                
                if not main_content:
                    main_content = soup.body if soup.body else soup
                
                # Get text content
                text = main_content.get_text(separator=" ", strip=True)
                
                # Clean up whitespace
                text = " ".join(text.split())
                
                return {
                    "title": title,
                    "content": text[:5000]  # Limit content length
                }
                
            except Exception as e:
                # Ensure browser is closed even on error
                try:
                    await browser.close()
                except:
                    pass
                raise e
                
    except ImportError:
        # Playwright not installed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JavaScript rendering not available. Playwright is required for JavaScript-heavy sites."
        )
    except Exception as e:
        logger.warning("Playwright scraping failed", url=url, error=str(e))
        raise


async def scrape_website_content(url: str) -> dict:
    """
    Scrape website content for summarization.
    
    Tries regular HTTP scraping first, then falls back to Playwright
    for JavaScript-rendered sites if content is minimal.
    
    Args:
        url: Website URL (will auto-add https:// if missing)
        
    Returns:
        Dictionary with title and content
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        # Normalize URL (add protocol if missing)
        normalized_url = normalize_url(url)
        
        # Step 1: Try regular HTTP scraping (fast, works for most sites)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(normalized_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            html = response.text
        
        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title
        title = None
        if soup.title:
            title = soup.title.get_text().strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract main content
        main_content = None
        for tag in ["main", "article", "[role='main']", ".content", "#content"]:
            element = soup.select_one(tag)
            if element:
                main_content = element
                break
        
        if not main_content:
            main_content = soup.body if soup.body else soup
        
        # Get text content
        text = main_content.get_text(separator=" ", strip=True)
        
        # Clean up whitespace
        text = " ".join(text.split())
        
        # Step 2: If content is minimal (< 200 chars), try Playwright for JS rendering
        if len(text) < 200:
            logger.info("Content is minimal, trying JavaScript rendering", url=normalized_url, content_length=len(text))
            try:
                playwright_result = await scrape_with_playwright(normalized_url)
                # Use Playwright result if it has more content
                if len(playwright_result.get("content", "")) > len(text):
                    logger.info("Playwright found more content", url=normalized_url, content_length=len(playwright_result.get("content", "")))
                    return playwright_result
                # Otherwise, use original result (at least we tried)
            except HTTPException:
                # Playwright not available or failed, use original result
                logger.debug("Playwright fallback failed, using original content", url=normalized_url)
            except Exception as e:
                logger.debug("Playwright fallback error, using original content", url=normalized_url, error=str(e))
        
        return {
            "title": title,
            "content": text[:5000]  # Limit content length
        }
        
    except httpx.RequestError as e:
        logger.error("Failed to scrape website - request error", url=url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch website: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        logger.error("Failed to scrape website - HTTP error", url=url, status_code=e.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch website: HTTP {e.response.status_code}"
        )
    except Exception as e:
        logger.error("Failed to scrape website", url=url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch website: {str(e)}"
        )


@router.post("/generate-keywords", response_model=KeywordGenerationResponse)
async def generate_keywords(
    request: KeywordGenerationRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate keywords based on a product description using LLM.
    
    This endpoint analyzes a product/service description and generates
    relevant keywords that could be used for lead searches.
    """
    try:
        llm = get_llm(temperature=0.3)  # Slight creativity for keyword generation
        
        system_prompt = """You are an expert at generating search keywords for lead generation.

Given a product or service description, generate relevant keywords that people might use when looking for that product or service on social media platforms like Reddit.

Focus on:
- Terms people would use when seeking the product/service
- Problem statements related to the product/service
- Industry-specific terminology
- Common search phrases

Return ONLY a JSON array of keywords, no explanation:
["keyword1", "keyword2", "keyword3", ...]"""

        user_message = f"""Product/Service Description:
{request.product_description}

Generate {request.max_keywords} relevant keywords for lead generation searches."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Parse JSON response
        if "```json" in content:
            parts = content.split("```json")
            if len(parts) > 1:
                content = parts[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1].split("```")[0].strip()
        
        keywords = json.loads(content)
        
        # Ensure it's a list and limit to max_keywords
        if isinstance(keywords, str):
            keywords = [keywords]
        elif not isinstance(keywords, list):
            keywords = list(keywords) if keywords else []
        
        # Limit to max_keywords
        keywords = keywords[:request.max_keywords]
        
        # Clean keywords
        keywords = [kw.strip() for kw in keywords if kw.strip()]
        
        if not keywords:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate keywords"
            )
        
        logger.info("Generated keywords", count=len(keywords), description_preview=request.product_description[:50])
        
        return KeywordGenerationResponse(
            keywords=keywords,
            count=len(keywords)
        )
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse keyword generation response"
        )
    except Exception as e:
        logger.error("Failed to generate keywords", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate keywords: {str(e)}"
        )


@router.post("/website-summary", response_model=WebsiteSummaryResponse)
async def generate_website_summary(
    request: WebsiteSummaryRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate a concise summary of a website (50 words by default).
    
    This endpoint fetches a website, extracts its content, and uses LLM
    to generate a brief summary.
    
    Note: URLs without http:// or https:// will automatically have https:// added.
    """
    try:
        # Normalize URL (add protocol if missing)
        normalized_url = normalize_url(request.url)
        
        # Scrape website content
        website_data = await scrape_website_content(normalized_url)
        
        if not website_data.get("content"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No content found on website"
            )
        
        llm = get_llm(temperature=0.0)  # No creativity for summarization
        
        system_prompt = f"""You are an expert at summarizing websites concisely.

Generate a clear, informative summary of the website content in approximately {request.max_words} words.

Focus on:
- What the company/product/service does
- Key value propositions
- Main features or benefits

Keep it concise and factual."""

        user_message = f"""Website Title: {website_data.get('title', 'N/A')}

Website Content:
{website_data['content'][:3000]}

Generate a {request.max_words}-word summary of this website."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        summary = response.content.strip()
        
        # Count words
        word_count = len(summary.split())
        
        logger.info("Generated website summary", url=normalized_url, word_count=word_count)
        
        return WebsiteSummaryResponse(
            url=normalized_url,  # Return normalized URL (with protocol)
            summary=summary,
            word_count=word_count,
            title=website_data.get("title")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate website summary", url=request.url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate website summary: {str(e)}"
        )


@router.post("/semantic-queries", response_model=SemanticQueriesResponse)
async def generate_semantic_queries(
    request: SemanticQueriesRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate semantic queries that customers might ask about a website or business.
    
    This endpoint analyzes a website or business description and generates
    relevant questions, search queries, and problem statements that potential
    customers might use when looking for this business or its services.
    
    You can provide either:
    - A website URL (will scrape and analyze the website)
    - A business description (will analyze the description directly)
    
    The generated queries can be used for:
    - Understanding customer intent
    - SEO optimization
    - Content marketing
    - Lead generation searches
    """
    try:
        # Validate that at least one input is provided
        if not request.url and not request.business_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'url' or 'business_description' must be provided"
            )
        
        # Get business content
        business_content = None
        website_title = None
        normalized_url = None
        
        if request.url:
            # Scrape website content
            normalized_url = normalize_url(request.url)
            website_data = await scrape_website_content(normalized_url)
            business_content = website_data.get("content", "")
            website_title = website_data.get("title")
            
            if not business_content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No content found on website. Please provide a business_description instead."
                )
        else:
            # Use provided business description
            business_content = request.business_description
        
        # Build query type descriptions
        query_type_descriptions = {
            "question": "questions customers might ask (e.g., 'How does X work?', 'What is Y?')",
            "search_query": "search queries customers might use (e.g., 'best X service', 'affordable Y')",
            "problem_statement": "problems customers are trying to solve (e.g., 'need help with X', 'looking for Y solution')"
        }
        
        query_types_text = ", ".join([
            query_type_descriptions.get(qt, qt) 
            for qt in request.query_types 
            if qt in query_type_descriptions
        ])
        
        llm = get_llm(temperature=0.4)  # Moderate creativity for query generation
        
        system_prompt = """You are an expert at understanding customer intent and generating semantic queries.

Given information about a business, product, or service, generate realistic queries that potential customers might use when:
- Searching for this business online
- Asking questions about the product/service
- Looking for solutions to problems this business solves

Generate diverse queries that reflect different customer personas, intents, and stages of the buyer's journey.

Return ONLY a JSON array of queries, no explanation:
["query1", "query2", "query3", ...]"""

        # Build user message (avoid backslashes in f-string expressions)
        title_section = f"Website Title: {website_title}\n" if website_title else ""
        user_message = f"""Business Information:
{title_section}{business_content[:3000]}

Generate {request.max_queries} semantic queries that customers might ask or search for.
Include a mix of: {query_types_text}

Make the queries:
- Natural and realistic (how real customers would phrase them)
- Specific to this business/product/service
- Varied in intent (informational, transactional, problem-solving)
- Relevant to different customer personas"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Parse JSON response
        if "```json" in content:
            parts = content.split("```json")
            if len(parts) > 1:
                content = parts[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1].split("```")[0].strip()
        
        queries = json.loads(content)
        
        # Ensure it's a list and limit to max_queries
        if isinstance(queries, str):
            queries = [queries]
        elif not isinstance(queries, list):
            queries = list(queries) if queries else []
        
        # Limit to max_queries
        queries = queries[:request.max_queries]
        
        # Clean queries
        queries = [q.strip() for q in queries if q.strip()]
        
        if not queries:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate semantic queries"
            )
        
        logger.info(
            "Generated semantic queries",
            count=len(queries),
            url=normalized_url,
            has_business_description=bool(request.business_description)
        )
        
        return SemanticQueriesResponse(
            queries=queries,
            count=len(queries),
            url=normalized_url,
            title=website_title
        )
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse semantic queries response"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate semantic queries", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate semantic queries: {str(e)}"
        )

