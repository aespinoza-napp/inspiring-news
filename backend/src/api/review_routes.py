"""
Reviewing a draft: the corrector's metrics and its proposed corrections
(docs/decisions/writing.md, "Review"). Registered in main.py; the
endpoints are added with the review stage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.routes import require_storage_key

router = APIRouter(dependencies=[Depends(require_storage_key)])
