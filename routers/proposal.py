# python-lead-engine/routers/proposal.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional

from services.proposal_generator import generate_proposal_pdf

router = APIRouter()


class ModuleItem(BaseModel):
    name: str
    description: Optional[str] = ""
    timeline: Optional[str] = "2 weeks"
    price: Optional[float] = 0


class ProposalRequest(BaseModel):
    company_name: str
    email: Optional[str] = ""
    website: Optional[str] = ""
    country: Optional[str] = ""
    score: Optional[int] = 0
    tag: Optional[str] = "unscored"
    modules: List[ModuleItem] = []
    headcount: Optional[int] = 0
    prepared_for: Optional[str] = None   # override recipient name


@router.post("/generate-proposal", summary="Generate branded proposal PDF")
async def generate_proposal(payload: ProposalRequest):
    try:
        lead = {
            "company_name": payload.company_name,
            "email":        payload.email,
            "website":      payload.website,
            "country":      payload.country,
            "score":        payload.score,
            "tag":          payload.tag,
        }
        modules = [m.model_dump() for m in payload.modules]

        pdf_bytes = generate_proposal_pdf(
            lead=lead,
            modules=modules,
            headcount=payload.headcount or 0,
            prepared_for=payload.prepared_for,
        )

        filename = f"Proposal_{payload.company_name.replace(' ', '_')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))