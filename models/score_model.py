from pydantic import BaseModel
from typing import Optional


class ScoreRequest(BaseModel):
    company_name: Optional[str] = ""
    website:      Optional[str] = ""
    email:        Optional[str] = ""
    linkedin:     Optional[str] = ""
    country:      Optional[str] = ""
    check_website: Optional[bool] = True   # set False for instant scoring without site visit


class ScoreBreakdown(BaseModel):
    email_found:        int = 0
    linkedin_present:   int = 0
    has_contact_form:   int = 0
    mobile_responsive:  int = 0
    country_identified: int = 0
    clean_company_name: int = 0


class ScoreResponse(BaseModel):
    success:         bool
    score:           int
    tag:             str          # hot / warm / cold / unscored
    score_breakdown: ScoreBreakdown