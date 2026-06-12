from fastapi import APIRouter, HTTPException
from models.score_model import ScoreRequest, ScoreResponse, ScoreBreakdown
from services.scorer import score_and_analyze_lead

router = APIRouter()


@router.post("/score-lead", response_model=ScoreResponse)
async def score_lead_endpoint(body: ScoreRequest):
    """
    Score a single lead and return score (0-100) + tag + breakdown.

    Body fields (all optional):
        company_name  str
        website       str
        email         str
        linkedin      str
        country       str

    Returns:
        score           int   0-100
        tag             str   hot / warm / cold / unscored
        score_breakdown dict  points per signal
    """
    try:
        lead_dict = {
            "company_name": body.company_name or "",
            "website":      body.website      or "",
            "email":        body.email        or "",
            "linkedin":     body.linkedin     or "",
            "country":      body.country      or "",
        }

        result = await score_and_analyze_lead(lead_dict)

        breakdown = result.get("scoreBreakdown", {})

        return ScoreResponse(
            success=True,
            score=result["score"],
            tag=result["tag"],
            score_breakdown=ScoreBreakdown(
                email_found        = breakdown.get("emailFound",       0),
                linkedin_present   = breakdown.get("linkedinActive",   0),
                has_contact_form   = breakdown.get("websiteQuality",   0),
                mobile_responsive  = 0,
                country_identified = breakdown.get("companySize",      0),
                clean_company_name = breakdown.get("hiringSignals",    0),
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring error: {str(e)}")