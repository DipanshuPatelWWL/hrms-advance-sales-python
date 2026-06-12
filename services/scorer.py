"""
scorer.py  —  Lead scoring engine
Scores each lead 0-100 based on:
  - Email found        : 35 pts
  - LinkedIn present   : 20 pts
  - Website quality    : 20 pts  (has contact form, mobile responsive)
  - Country identified : 10 pts
  - Company name clean : 15 pts  (not a directory / blog title)
"""

import re
import httpx
import asyncio
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.playwright_helper import get_rendered_html
from utils.helpers import calculate_genuineness, detect_tech_stack


# ── Domains that indicate a directory / listicle result ──────────────────────
DIRECTORY_SIGNALS = [
    "best", "top", "review", "list", "compare", "vs", "ranked",
    "guide", "how to", "what is", "2024", "2025", "2026",
]

SKIP_TLDS = {".gov", ".edu", ".mil"}



async def get_domain_age_years(website_url: str) -> float | None:
    """
    WHOIS lookup to get domain creation date → age in years.
    Runs in executor to avoid blocking async event loop.
    Returns float years or None if lookup fails.
    """
    if not website_url:
        return None
    try:
        domain = urlparse(website_url).netloc.replace("www.", "")
        if not domain:
            return None

        loop = asyncio.get_event_loop()

        def _whois_lookup():
            import whois
            try:
                # pass timeout to whois if possible, though not all versions support it
                w = whois.whois(domain)
                creation = w.creation_date
                if isinstance(creation, list):
                    creation = creation[0]
                if creation:
                    if creation.tzinfo is None:
                        creation = creation.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    return (now - creation).days / 365.25
            except:
                pass
            return None

        age = await asyncio.wait_for(
            loop.run_in_executor(None, _whois_lookup),
            timeout=5.0
        )
        return age
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None

async def analyze_website(website_url: str) -> dict:

    result = {
        "hasContactForm": False,
        "isMobileResponsive": False,
        "bonusEmails": [],
        "techStack": [],
    }

    if not website_url:
        return result

    pages_to_check = [
        website_url,
        urljoin(website_url, "/contact"),
        urljoin(website_url, "/contact-us"),
        urljoin(website_url, "/about"),
        urljoin(website_url, "/about-us"),
        urljoin(website_url, "/team"),
        urljoin(website_url, "/company"),
    ]

    email_pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )

    skip_email_domains = {
        "sentry.io",
        "example.com",
        "domain.com",
        "wixpress.com",
        "squarespace.com",
        "wordpress.com",
        "amazonaws.com",
        "googletagmanager.com",
        "intercom.io",
        "hubspot.com",
        "mailchimp.com",
        "zendesk.com",
        "cloudflare.com",
        "segment.com",
        "mixpanel.com",
        "doubleclick.net",
        "w3.org",
        "schema.org",
    }

    for page_url in pages_to_check:

        try:

            html = await get_rendered_html(page_url)

            if not html:
                continue

            soup = BeautifulSoup(
                html,
                "html.parser"
            )

            if page_url == website_url:

                viewport = soup.find(
                    "meta",
                    attrs={"name": "viewport"}
                )

                if viewport:
                    result["isMobileResponsive"] = True

                # ── Full tech stack detection via helpers.py fingerprints ──
                result["techStack"] = detect_tech_stack(html)

            forms = soup.find_all("form")

            for form in forms:

                inputs = form.find_all("input")

                input_types = [
                    i.get("type", "").lower()
                    for i in inputs
                ]

                input_names = [
                    i.get("name", "").lower()
                    for i in inputs
                ]

                if (
                    "email" in input_types
                    or "email" in input_names
                    or any("email" in n for n in input_names)
                ):
                    result["hasContactForm"] = True
                    break

            for a in soup.find_all("a", href=True):

                href = a["href"]

                if href.startswith("mailto:"):

                    email = href[7:].split("?")[0].strip().lower()

                    domain = (
                        email.split("@")[-1]
                        if "@" in email
                        else ""
                    )

                    if (
                        "@" in email
                        and domain not in skip_email_domains
                        and len(email) < 80
                    ):
                        result["bonusEmails"].append(email)

            emails_in_page = email_pattern.findall(html)

            for email in emails_in_page:

                email = email.lower()

                domain = email.split("@")[-1]

                if (
                    domain not in skip_email_domains
                    and not any(
                        s in domain
                        for s in ["sentry", "example", "test"]
                    )
                    and len(email) < 80
                ):
                    result["bonusEmails"].append(email)

        except Exception:
            continue

    seen = set()
    unique_emails = []

    for e in result["bonusEmails"]:

        if e not in seen:
            seen.add(e)
            unique_emails.append(e)

    result["bonusEmails"] = sorted(
        unique_emails,
        key=len
    )[:3]

    return result


def score_lead(lead: dict, website_analysis: dict) -> dict:
    """
    Score a lead 0-100 and return full breakdown.
    lead keys: company_name, email, linkedin, country, website
    """
    breakdown = {
        "emailFound": 0,
        "linkedinActive": 0,
        "websiteQuality": 0,
        "companySize": 0,
        "hiringSignals": 0,
    }

    # ── Email found: 35 pts ──────────────────────────────────────────────────
    email = lead.get("email", "") or ""
    if email and "@" in email:
        breakdown["emailFound"] = 35

    # ── LinkedIn present: 20 pts ─────────────────────────────────────────────
    linkedin = lead.get("linkedin", "") or ""
    if linkedin and "linkedin.com/company" in linkedin:
        breakdown["linkedinActive"] = 20
    elif linkedin and "linkedin.com" in linkedin:
        breakdown["linkedinActive"] = 10

    # ── Website quality: up to 20 pts ────────────────────────────────────────
    website = lead.get("website", "") or ""
    wq = 0
    if website:
        wq += 8   # has a website at all
        if website_analysis.get("hasContactForm"):
            wq += 6
        if website_analysis.get("isMobileResponsive"):
            wq += 6
    breakdown["websiteQuality"] = wq

    # ── Country identified: 10 pts ───────────────────────────────────────────
    country = lead.get("country", "") or ""
    if country and len(country) > 1:
        breakdown["companySize"] = 10

    # ── Company name quality: 15 pts ─────────────────────────────────────────
    # Deduct if it looks like a blog title / directory
    name = (lead.get("company_name", "") or "").lower()
    is_clean = not any(signal in name for signal in DIRECTORY_SIGNALS)
    if is_clean and name:
        breakdown["hiringSignals"] = 15

    total = sum(breakdown.values())
    total = min(total, 100)

    if total >= 70:
        tag = "hot"
    elif total >= 40:
        tag = "warm"
    elif total > 0:
        tag = "cold"
    else:
        tag = "unscored"

    return {
        "score": total,
        "tag": tag,
        "scoreBreakdown": breakdown,
    }


async def score_and_analyze_lead(lead: dict) -> dict:
    """
    Full pipeline: analyze website → WHOIS → score → genuineness → return enriched lead data.
    """
    website = lead.get("website", "") or ""

    # Run website analysis + WHOIS concurrently
    analysis, domain_age_years = await asyncio.gather(
        analyze_website(website),
        get_domain_age_years(website),
    )

    # Use bonus emails if the scraper didn't find one
    email = lead.get("email", "") or ""
    if not email and analysis["bonusEmails"]:
        email = analysis["bonusEmails"][0]

    enriched_lead = {**lead, "email": email}
    scoring = score_lead(enriched_lead, analysis)

    # Genuineness check using all collected signals
    genuineness = calculate_genuineness(enriched_lead, domain_age_years)

    return {
        **enriched_lead,
        **scoring,
        **genuineness,
        "websiteAnalysis": {
            "hasContactForm":    analysis["hasContactForm"],
            "isMobileResponsive": analysis["isMobileResponsive"],
            "techStack":         analysis["techStack"],
            "domainAgeYears":    domain_age_years,
            "domainCreatedYear": (
                int(datetime.now(timezone.utc).year - domain_age_years)
                if domain_age_years is not None else None
            ),
            "lastAnalyzed":  None,
            "pageSpeedScore": None,
        },
    }