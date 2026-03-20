"""FastAPI application entry point for Aetherix.

IMPORTANT: After cloning the vintasoftware/nextjs-fastapi-template, this file
will already exist. The key addition for Story 1.1 is registering the RFC 7807
error handler below.

Add the following lines to the app created by the template:
"""
# ─── Story 1.1 Addition ───────────────────────────────────────────────────────
# After the `app = FastAPI(...)` line in the template's main.py, add:
#
# from app.core.error_handlers import problem_details_handler
# from fastapi import HTTPException
# app.add_exception_handler(HTTPException, problem_details_handler)
#
# This ensures ALL HTTP exceptions are formatted as RFC 7807 Problem Details.
# Architecture constraint: [Source: architecture.md#Process-Patterns]
# ─────────────────────────────────────────────────────────────────────────────
