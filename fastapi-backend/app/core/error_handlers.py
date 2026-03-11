"""RFC 7807 Problem Details error handler.

All HTTP exceptions from the Aetherix FastAPI backend MUST be formatted
as RFC 7807 Problem Details JSON. Register this handler in main.py.

Architecture constraint: [Source: architecture.md#Process-Patterns]
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


async def problem_details_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format all HTTPExceptions as RFC 7807 Problem Details.

    Returns a JSON response with fields: type, title, status, detail.
    The frontend and all future API consumers MUST parse this format — never
    rely on FastAPI's default {"detail": "..."} shape.

    Example response:
        {
            "type": "https://aetherix.io/errors/404",
            "title": "HTTPException",
            "status": 404,
            "detail": "Item not found"
        }
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://aetherix.io/errors/{exc.status_code}",
            "title": type(exc).__name__,
            "status": exc.status_code,
            "detail": exc.detail,
        },
    )
