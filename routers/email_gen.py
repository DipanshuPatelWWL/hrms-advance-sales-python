from fastapi import APIRouter, HTTPException
from models.email_model import EmailRequest, EmailResponse
from services.ai_email import generate_email

router = APIRouter()


@router.post("/generate-email", response_model=EmailResponse)
async def generate_email_endpoint(body: EmailRequest):
    """
    Generate a personalised outreach email for a lead.

    Body fields (all optional):
        company_name  str   — company to email
        website       str   — their website URL
        email         str   — their email address
        country       str   — their country
        linkedin      str   — their LinkedIn URL
        score         int   — lead score 0-100
        tag           str   — hot / warm / cold / unscored
        service       str   — what service you are pitching

    Returns:
        subject       str   — email subject line
        body          str   — full email body
        generated_by  str   — "claude-ai" | "openai" | "template"
    """
    if not body.company_name and not body.website:
        raise HTTPException(
            status_code=400,
            detail="At least company_name or website is required"
        )

    try:
        result = await generate_email(
            company_name = body.company_name or "",
            website      = body.website      or "",
            email        = body.email        or "",
            country      = body.country      or "",
            linkedin     = body.linkedin     or "",
            score        = body.score        or 0,
            tag          = body.tag          or "unscored",
            service      = body.service      or "",
        )

        return EmailResponse(
            success      = True,
            subject      = result["subject"],
            body         = result["body"],
            generated_by = result["generated_by"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation error: {str(e)}")