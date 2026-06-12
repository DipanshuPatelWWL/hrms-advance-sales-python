"""
routers/website.py — Day 18 update
Adds: POST /api/talking-points
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.website_analyzer import analyze_website
from services.opportunity_engine import detect_opportunities, generate_pitch_summary

router = APIRouter()


class AnalyzeRequest(BaseModel):
    url: str
    company_name: Optional[str] = ""
    lead_id: Optional[str] = None


class TalkingPointsRequest(BaseModel):
    company_name: str
    website_analysis: dict
    html_content: Optional[str] = ""


@router.post("/analyze-website")
async def analyze_website_endpoint(req: AnalyzeRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    url = req.url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    result = await analyze_website(url, company_name=req.company_name or "")
    if result.get("error") and not result.get("techStack"):
        raise HTTPException(status_code=422, detail=result["error"])
    return {
        "success": True,
        "url": url,
        "techStack": result["techStack"],
        "isMobileResponsive": result["isMobileResponsive"],
        "hasContactForm": result["hasContactForm"],
        "hasSSL": result["hasSSL"],
        "estimatedSpeed": result["estimatedSpeed"],
        "pageSpeedScore": result["pageSpeedScore"],
        "externalScripts": result["externalScripts"],
        "opportunities": result["opportunities"],
        "pitchSummary": result["pitchSummary"],
        "lastAnalyzed": result["lastAnalyzed"],
        "error": result.get("error"),
    }


@router.post("/talking-points")
async def generate_talking_points(req: TalkingPointsRequest):
    if not req.company_name.strip():
        raise HTTPException(status_code=400, detail="company_name is required")
    opportunities = detect_opportunities(
        website_analysis=req.website_analysis,
        html_content=req.html_content or "",
        company_name=req.company_name,
    )
    summary = generate_pitch_summary(opportunities, req.company_name)
    return {
        "success": True,
        "company_name": req.company_name,
        "opportunities": opportunities,
        "pitchSummary": summary,
        "total": len(opportunities),
    }