"""
Global exception handler and error middleware.
"""

from typing import Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.logger import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Base API error with structured response."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = None,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "internal_error"
        self.details = details or {}
        super().__init__(self.message)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled exceptions.
    
    Args:
        request: The request that caused the exception
        exc: The exception that was raised
        
    Returns:
        JSONResponse: Structured error response
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An internal server error occurred",
                "error_code": "internal_error",
                "path": request.url.path,
                "method": request.method
            }
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handler for HTTP exceptions.
    
    Args:
        request: The request that caused the exception
        exc: The HTTP exception
        
    Returns:
        JSONResponse: Structured error response
    """
    logger.warning(
        "HTTP exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=str(exc.detail)
    )
    
    # Handle structured error responses
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "error_code": f"http_{exc.status_code}",
                "path": request.url.path
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler for validation errors.
    
    Args:
        request: The request that caused the validation error
        exc: The validation exception
        
    Returns:
        JSONResponse: Structured error response with validation details
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg"),
            "type": error.get("type")
        })
    
    logger.warning(
        "Validation error",
        path=request.url.path,
        method=request.method,
        errors=errors
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation error",
                "error_code": "validation_error",
                "details": errors
            }
        }
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handler for APIError exceptions.
    
    Args:
        request: The request that caused the error
        exc: The API error
        
    Returns:
        JSONResponse: Structured error response
    """
    logger.warning(
        "API error",
        path=request.url.path,
        method=request.method,
        error_code=exc.error_code,
        message=exc.message
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "error_code": exc.error_code,
                "details": exc.details
            }
        }
    )

