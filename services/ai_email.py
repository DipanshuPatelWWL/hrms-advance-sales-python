"""
ai_email.py — AI Email Generation Service
==========================================
Tries in order:
  1. Anthropic Claude API  (if ANTHROPIC_API_KEY set)
  2. OpenAI API            (if OPENAI_API_KEY set)
  3. Built-in template     (always works, no API key needed)

The template fallback means this works on Day 10 even before you
add API keys — you can add keys later in .env to upgrade to AI.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# ── Your company details (edit these in .env or directly here) ────────────────
YOUR_COMPANY    = os.getenv("YOUR_COMPANY_NAME",    "Our Company")
YOUR_SERVICE    = os.getenv("YOUR_SERVICE",         "custom HRMS and business software")
YOUR_NAME       = os.getenv("YOUR_SENDER_NAME",     "The Sales Team")
YOUR_WEBSITE    = os.getenv("YOUR_COMPANY_WEBSITE", "")


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_prompt(company_name: str, website: str, country: str, tag: str) -> str:
    urgency = {
        "hot":  "This is a high-priority lead. Write with confidence and a clear call to action.",
        "warm": "This is a warm lead. Be friendly and professional.",
        "cold": "This is a cold outreach. Be brief, polite, and non-pushy.",
    }.get(tag, "Be professional and concise.")

    return f"""Write a professional B2B cold outreach email for a sales representative.

Company being contacted: {company_name}
Their website: {website or "unknown"}
Their country: {country or "unknown"}
Our company: {YOUR_COMPANY}
What we offer: {YOUR_SERVICE}
Lead priority: {tag} ({urgency})

Requirements:
- Subject line: short, specific, no clickbait
- Body: 3-4 short paragraphs maximum
- Mention their company name naturally
- Explain briefly what we do and how it helps THEM specifically
- One clear call to action (15-minute call)
- Professional sign-off with [Your Name] placeholder
- Do NOT use generic phrases like "I hope this finds you well"
- Do NOT use excessive exclamation marks
- Sound human, not like a template

Respond ONLY in this exact format — no other text before or after:
SUBJECT: <subject line here>
BODY:
<email body here>"""


# ── Claude API ────────────────────────────────────────────────────────────────
async def _generate_with_claude(prompt: str) -> dict:
    """Call Anthropic Claude API to generate email."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["content"][0]["text"].strip()
        return _parse_response(text, "claude-ai")


# ── OpenAI API ────────────────────────────────────────────────────────────────
async def _generate_with_openai(prompt: str) -> dict:
    """Call OpenAI API to generate email."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":      "gpt-3.5-turbo",
                "max_tokens": 600,
                "messages": [
                    {"role": "system", "content": "You are a professional B2B sales email writer."},
                    {"role": "user",   "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        return _parse_response(text, "openai")


# ── Response parser ───────────────────────────────────────────────────────────
def _parse_response(text: str, source: str) -> dict:
    """
    Parse AI response in format:
    SUBJECT: <subject>
    BODY:
    <body>
    """
    subject = ""
    body    = ""

    lines = text.strip().splitlines()
    in_body = False

    for i, line in enumerate(lines):
        if line.upper().startswith("SUBJECT:"):
            subject = line[8:].strip()
        elif line.upper().startswith("BODY:"):
            in_body = True
            # Body may start on same line or next line
            rest = line[5:].strip()
            if rest:
                body = rest
        elif in_body:
            body += ("\n" if body else "") + line

    body = body.strip()

    # Fallback if parsing failed
    if not subject:
        subject = f"Partnership Opportunity – {YOUR_COMPANY}"
    if not body:
        body = text  # use full response as body

    return {"subject": subject, "body": body, "generated_by": source}


# ── Template fallback ─────────────────────────────────────────────────────────
def _generate_template(company_name: str, website: str, country: str, tag: str) -> dict:
    """
    Professional template — no API key needed.
    Customises based on tag (hot / warm / cold).
    """
    intro = {
        "hot":  f"I came across {company_name} while researching leading companies{' in ' + country if country else ''} and I wanted to reach out directly.",
        "warm": f"I recently came across {company_name}{' at ' + website if website else ''} and thought there might be a great fit between our work.",
        "cold": f"I hope this message finds you well. I came across {company_name} and wanted to introduce ourselves briefly.",
    }.get(tag, f"I came across {company_name} and wanted to reach out.")

    subject = f"Quick question for {company_name}"

    body = f"""Hi,

{intro}

We are {YOUR_COMPANY} and we specialise in {YOUR_SERVICE}. We work with companies like yours to streamline operations, improve team efficiency, and reduce manual overhead — all through custom software built around your specific workflow.

I would love to learn more about how {company_name} currently handles these processes and share how we have helped similar organisations. Would you be open to a quick 15-minute call this week or next?

Looking forward to hearing from you.

Best regards,
[Your Name]
{YOUR_COMPANY}{chr(10) + YOUR_WEBSITE if YOUR_WEBSITE else ""}"""

    return {"subject": subject, "body": body, "generated_by": "template"}


# ── Main entry point ──────────────────────────────────────────────────────────
async def generate_email(
    company_name: str = "",
    website:      str = "",
    email:        str = "",
    country:      str = "",
    linkedin:     str = "",
    score:        int = 0,
    tag:          str = "unscored",
    service:      str = "",
) -> dict:
    """
    Generate outreach email for a lead.
    Returns { subject, body, generated_by }
    """
    prompt = _build_prompt(company_name, website, country, tag)

    # Try Claude first
    if ANTHROPIC_API_KEY:
        try:
            result = await _generate_with_claude(prompt)
            print(f"✅ Email generated via Claude for: {company_name}")
            return result
        except Exception as e:
            print(f"⚠️  Claude API failed: {e} — trying OpenAI")

    # Try OpenAI second
    if OPENAI_API_KEY:
        try:
            result = await _generate_with_openai(prompt)
            print(f"✅ Email generated via OpenAI for: {company_name}")
            return result
        except Exception as e:
            print(f"⚠️  OpenAI API failed: {e} — using template")

    # Always falls back to template
    print(f"📝 Using template for: {company_name}")
    return _generate_template(company_name, website, country, tag)