"""
routers/leads.py  —  FastAPI routes for lead generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.scraper import find_and_score_leads
from utils.helpers import normalize_country
from typing import Optional, List

router = APIRouter()


class FindLeadsRequest(BaseModel):
    keyword: str
    limit: Optional[int] = 20
    source: Optional[str] = "web"
    location: Optional[str] = ""
    search_mode: Optional[str] = "fast"
    # ── New filter fields ──────────────────────────────────────────────────
    country: Optional[str] = ""
    cities: Optional[List[str]] = []
    postal_codes: Optional[List[str]] = Field([], alias="postalCodes")
    domain_year_from: Optional[int] = None
    domain_year_to: Optional[int] = None
    required_techs: Optional[List[str]] = []
    genuineness_min: Optional[int] = 0

    class Config:
        populate_by_name = True


@router.post("/find-leads")
async def find_leads(req: FindLeadsRequest):
    if not req.keyword.strip():
        raise HTTPException(status_code=400, detail="keyword is required")

    limit = max(1, min(req.limit, 50))
    print(f"[ROUTE] find-leads started for keyword: {req.keyword}")

    # Route to the correct scraper based on source
    if req.source == "foursquare":
        from services.foursquare_scraper import find_leads_foursquare
        raw_leads = await find_leads_foursquare(
            req.keyword.strip(), limit,
            location=req.location,
            search_mode=req.search_mode
        )
        # Apply same filters as web scraper
        leads = []
        normalized_filter_country = normalize_country(req.country) if req.country else ""
        
        for lead in raw_leads:
            if normalized_filter_country:
                raw_detected = lead.get("country") or "Unknown"
                normalized_detected = normalize_country(raw_detected)
                
                # Lenient check: Pass if Unknown or if exact match
                if normalized_detected != "Unknown" and normalized_detected.lower() != normalized_filter_country.lower():
                    continue
            
            if req.cities:
                lead_city = (lead.get("city") or "").lower().strip()
                if lead_city and lead_city not in [c.lower().strip() for c in req.cities]:
                    continue

            if req.postal_codes:
                lead_pc = (lead.get("postal_code") or "").lower().strip()
                if lead_pc and lead_pc not in [p.lower().strip() for p in req.postal_codes]:
                    continue

            year = (lead.get("websiteAnalysis") or {}).get("domainCreatedYear")
            if year is not None:
                if req.domain_year_from and year < req.domain_year_from:
                    continue
                if req.domain_year_to and year > req.domain_year_to:
                    continue
            if req.required_techs:
                lead_techs = [(t.lower()) for t in (lead.get("websiteAnalysis") or {}).get("techStack", [])]
                if not any(rt.lower() in lead_techs for rt in req.required_techs):
                    continue
            if req.genuineness_min and (lead.get("genuinenessScore") or 0) < req.genuineness_min:
                continue
            leads.append(lead)
    else:
        leads = await find_and_score_leads(
            keyword=req.keyword.strip(),
            limit=limit,
            country=req.country or "",
            cities=req.cities or [],
            postal_codes=req.postal_codes or [],
            domain_year_from=req.domain_year_from,
            domain_year_to=req.domain_year_to,
            required_techs=req.required_techs or [],
            genuineness_min=req.genuineness_min or 0,
        )

    print(f"[ROUTE] find-leads returning {len(leads)} leads")
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={
        "success":     True,
        "keyword":     req.keyword,
        "source":      req.source,
        "total_found": len(leads),
        "leads":       leads,
    })
    print(f"[ROUTE] find-leads response object created")
    return resp


@router.get("/health")
async def health():
    return {"status": "ok", "service": "lead-generation-engine"}
