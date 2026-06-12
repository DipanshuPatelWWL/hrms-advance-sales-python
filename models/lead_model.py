from pydantic import BaseModel, HttpUrl
from typing import Optional, List


# ─── Request ──────────────────────────────────────────────────────────────────
class FindLeadsRequest(BaseModel):
    keyword: str                  # e.g. "Recruitment Companies UK"
    limit: Optional[int] = 20    # max leads to return


# ─── Single lead result ───────────────────────────────────────────────────────
class LeadResult(BaseModel):
    company_name: str
    website: Optional[str] = ""
    email: Optional[str] = ""
    linkedin: Optional[str] = ""
    country: Optional[str] = ""
    source_url: Optional[str] = ""   # the search result URL we found it from
    score: Optional[int] = 0
    tag: Optional[str] = "unscored"  # hot / warm / cold / unscored


# ─── Response ─────────────────────────────────────────────────────────────────
class FindLeadsResponse(BaseModel):
    success: bool
    keyword: str
    total_found: int
    leads: List[LeadResult]