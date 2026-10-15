"""
Approving and publishing a draft, and the public view of what was
published (docs/decisions/writing.md, "Publishing"). Registered in
main.py; the endpoints are added with the publishing stage.

No router-wide API key: the public reader's endpoints must stay open,
as /reader/articles is. Each private endpoint declares the key itself.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
