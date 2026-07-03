"""Uvicorn entry point.

    uvicorn main:app --reload

Kept intentionally thin: all construction lives in core.application.
"""

from core.application import create_app

app = create_app()
