"""
website_analyzer.py — Day 18 update
Now calls opportunity_engine for richer talking points
"""

import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone
from services.opportunity_engine import detect_opportunities, generate_pitch_summary


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

TECH_FINGERPRINTS = {
    "WordPress":        ["wp-content", "wp-includes", "wordpress"],
    "Shopify":          ["cdn.shopify.com", "shopify.com/s/"],
    "Wix":              ["wix.com", "wixstatic.com"],
    "Squarespace":      ["squarespace.com", "squarespace-cdn.com"],
    "Webflow":          ["webflow.com"],
    "Joomla":           ["/media/jui/", "Joomla!"],
    "Drupal":           ["Drupal.settings", "/sites/default/files/"],
    "React":            ["__REACT", "react-dom", "_reactRootContainer"],
    "Next.js":          ["__NEXT_DATA__", "_next/static"],
    "Vue.js":           ["__vue__", "vue.min.js"],
    "Angular":          ["ng-version", "angular.min.js"],
    "jQuery":           ["jquery.min.js", "jquery-"],
    "Google Analytics": ["google-analytics.com", "gtag(", "GoogleAnalyticsObject"],
    "HubSpot":          ["hubspot.com/", "hs-scripts.com"],
    "Hotjar":           ["hotjar.com", "hjSiteSettings"],
    "WooCommerce":      ["woocommerce", "wc-"],
    "Bootstrap":        ["bootstrap.min.css", "bootstrap.min.js"],
    "Tailwind":         ["tailwindcss"],
    "Cloudflare":       ["cloudflare", "__cfduid"],
}


async def analyze_website(url: str, company_name: str = "") -> dict:
    """
    Full website analysis with opportunity detection and talking points.
    """
    result = {
        "url": url,
        "techStack": [],
        "isMobileResponsive": None,
        "hasContactForm": None,
        "hasSSL": url.startswith("https://"),
        "estimatedSpeed": None,
        "pageSpeedScore": None,
        "externalScripts": 0,
        "opportunities": [],
        "pitchSummary": "",
        "lastAnalyzed": None,
        "error": None,
    }

    if not url or not url.startswith("http"):
        result["error"] = "Invalid URL"
        return result

    full_html = ""
    contact_html = ""

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True, headers=HEADERS,
    ) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                full_html = resp.text
        except Exception as e:
            result["error"] = f"Failed to fetch: {str(e)[:100]}"
            return result

        for contact_url in [urljoin(url, "/contact"), urljoin(url, "/contact-us")]:
            try:
                cr = await client.get(contact_url)
                if cr.status_code == 200:
                    contact_html = cr.text
                    break
            except Exception:
                pass

    if not full_html:
        result["error"] = "Empty response"
        return result

    soup = BeautifulSoup(full_html, "html.parser")
    html_lower = full_html.lower()

    # ── Tech stack ───────────────────────────────────────────────────────────
    detected = []
    for tech, fingerprints in TECH_FINGERPRINTS.items():
        for fp in fingerprints:
            if fp.lower() in html_lower:
                detected.append(tech)
                break
    result["techStack"] = list(dict.fromkeys(detected))[:8]

    # ── Mobile responsive ────────────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": re.compile(r"viewport", re.I)})
    if viewport:
        content = viewport.get("content", "").lower()
        result["isMobileResponsive"] = "width=device-width" in content
    else:
        result["isMobileResponsive"] = False

    # ── Contact form ─────────────────────────────────────────────────────────
    search_soup = BeautifulSoup(full_html + contact_html, "html.parser")
    has_form = False
    for form in search_soup.find_all("form"):
        inputs = form.find_all("input")
        all_attrs = (
            [i.get("type", "").lower() for i in inputs]
            + [i.get("name", "").lower() for i in inputs]
            + [i.get("id", "").lower() for i in inputs]
        )
        if any("email" in a or "contact" in a for a in all_attrs):
            has_form = True
            break
    mailto_links = [a for a in soup.find_all("a", href=True) if "mailto:" in a["href"]]
    result["hasContactForm"] = has_form or len(mailto_links) > 0

    # ── SSL ──────────────────────────────────────────────────────────────────
    result["hasSSL"] = url.startswith("https://")

    # ── Speed estimate ───────────────────────────────────────────────────────
    external = [s for s in soup.find_all("script", src=True) if "http" in s.get("src", "")]
    result["externalScripts"] = len(external)
    if len(external) <= 5:
        result["estimatedSpeed"] = "fast"
        result["pageSpeedScore"] = 85
    elif len(external) <= 12:
        result["estimatedSpeed"] = "medium"
        result["pageSpeedScore"] = 65
    else:
        result["estimatedSpeed"] = "slow"
        result["pageSpeedScore"] = 40

    # ── Opportunity detection (Day 18) ───────────────────────────────────────
    opportunities = detect_opportunities(
        website_analysis=result,
        html_content=full_html,
        company_name=company_name,
    )
    result["opportunities"] = opportunities

    # ── Pitch summary ────────────────────────────────────────────────────────
    result["pitchSummary"] = generate_pitch_summary(opportunities, company_name)

    result["lastAnalyzed"] = datetime.now(timezone.utc).isoformat()
    return result