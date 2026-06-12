"""
opportunity_engine.py — Opportunity detection + talking points generator
Day 18-19

Detects gaps in a company's tech/website and generates
specific sales talking points for each opportunity.

100% FREE — no API needed. Rule-based + template talking points.
"""

from typing import Optional


# ── HRMS / HR software detection ─────────────────────────────────────────────
HRMS_SIGNALS = [
    # Known HRMS/HR platforms
    "workday", "bamboohr", "hibob", "personio", "namely",
    "gusto", "rippling", "adp.com", "ceridian", "kronos",
    "sap successfactors", "oracle hcm", "zenefits", "paychex",
    "greenhouse", "lever.co", "ashby", "teamtailor",
    "factorial", "cezanne", "breathehr", "peoplehr",
    "iris hr", "access people", "cascade", "itrent",
    # Generic HR signals
    "hris", "hrms", "hr software", "payroll software",
    "employee portal", "staff portal", "workforce management",
    "time and attendance", "people management platform",
]

RECRUITMENT_ATS_SIGNALS = [
    "applicant tracking", "ats ", "job board", "careers portal",
    "vacancy management", "recruitment software", "talent acquisition",
    "greenhouse.io", "lever.co", "workable", "recruitee",
    "smartrecruiters", "jazz hr", "breezy hr",
]

# ── Outdated tech signals ─────────────────────────────────────────────────────
OUTDATED_TECH = {
    "jQuery": "jQuery is a 2006-era JavaScript library. Modern sites use React, Vue, or native JS.",
    "Joomla": "Joomla is an aging CMS with limited modern integrations and slower update cycles.",
    "Drupal": "Drupal is complex to maintain and has a smaller talent pool than modern alternatives.",
    "Flash": "Adobe Flash is discontinued since 2020. Any Flash content is now broken.",
}

MODERN_REPLACEMENTS = {
    "jQuery": "React or Vue.js for better performance and maintainability",
    "Joomla": "WordPress or Webflow for easier management and better integrations",
    "Drupal": "WordPress or a headless CMS for simpler content management",
}

# ── Talking point templates ───────────────────────────────────────────────────
TALKING_POINTS = {

    "no_hrms": {
        "title": "No HRMS Detected",
        "icon": "🏢",
        "severity": "critical",
        "opener": "I noticed {company} doesn't appear to be using a dedicated HR management system.",
        "pain_points": [
            "Manual HR processes cost an average of 40% more in admin time than automated systems.",
            "Without a centralised HRMS, attendance tracking and payroll errors are 3x more common.",
            "Employee self-service portals reduce HR queries by up to 60% — freeing your team for strategic work.",
            "Compliance risks increase significantly without automated leave and contract management.",
        ],
        "our_solution": "Our HRMS handles attendance, payroll, leave, daily reports, and employee self-service — all in one platform built specifically for companies your size.",
        "question": "How does {company} currently handle employee attendance and leave tracking?",
    },

    "no_mobile": {
        "title": "Not Mobile Responsive",
        "icon": "📱",
        "severity": "high",
        "opener": "I noticed {company}'s website isn't optimised for mobile devices.",
        "pain_points": [
            "Over 60% of web traffic now comes from mobile devices.",
            "Google penalises non-mobile sites in search rankings — affecting how candidates and clients find you.",
            "A poor mobile experience increases bounce rate by up to 70%.",
        ],
        "our_solution": "Our employee portal is fully mobile-first — staff can clock in, request leave, and check payslips from any device.",
        "question": "Do your employees need to access HR systems on their phones? We've found most companies benefit hugely from mobile HR access.",
    },

    "no_contact_form": {
        "title": "No Contact Form Found",
        "icon": "📬",
        "severity": "medium",
        "opener": "I couldn't find an easy way to contact {company} on your website.",
        "pain_points": [
            "Companies without contact forms lose an estimated 25% of inbound enquiries.",
            "Prospects who can't find contact info often move on to a competitor within 30 seconds.",
        ],
        "our_solution": "Our HRMS includes a built-in helpdesk module so employees and clients always have a clear way to raise requests.",
        "question": "Is your team finding it hard to manage inbound queries from candidates or clients?",
    },

    "no_analytics": {
        "title": "No Analytics Tracking",
        "icon": "📊",
        "severity": "medium",
        "opener": "It looks like {company} isn't tracking website performance with analytics tools.",
        "pain_points": [
            "Without analytics, there's no way to know which job postings or services attract the most interest.",
            "Companies flying blind on traffic data can't optimise their hiring or client acquisition funnel.",
            "Competitor benchmarking becomes impossible without baseline performance data.",
        ],
        "our_solution": "Our platform includes built-in reporting dashboards for HR metrics — attendance trends, leave patterns, payroll summaries — so you always know what's happening in your team.",
        "question": "How does {company} currently measure team performance and HR KPIs?",
    },

    "outdated_tech": {
        "title": "Outdated Technology Stack",
        "icon": "⚙️",
        "severity": "medium",
        "opener": "I noticed {company}'s website is built on some older technologies.",
        "pain_points": [
            "Older tech stacks often struggle to integrate with modern HR APIs and payroll providers.",
            "Legacy systems require expensive custom development for even basic integrations.",
            "Security vulnerabilities in outdated frameworks increase compliance risk.",
        ],
        "our_solution": "Our HRMS uses modern APIs and integrates with existing payroll, accounting, and CRM systems out of the box — no custom development needed.",
        "question": "Has {company} had difficulty connecting your existing systems together?",
    },

    "no_ssl": {
        "title": "No SSL Certificate",
        "icon": "🔒",
        "severity": "high",
        "opener": "I noticed {company}'s website doesn't have an SSL certificate (HTTPS).",
        "pain_points": [
            "Google Chrome marks non-HTTPS sites as 'Not Secure' — which damages trust with candidates and clients.",
            "Any data submitted through your website (CVs, contact forms) is sent unencrypted.",
            "GDPR and data protection laws require secure data transmission — non-HTTPS puts you at risk.",
        ],
        "our_solution": "All data in our HRMS is encrypted in transit and at rest — we're GDPR compliant by design.",
        "question": "Is data security and GDPR compliance something {company} is actively managing?",
    },

    "slow_website": {
        "title": "Slow Website Performance",
        "icon": "🐢",
        "severity": "low",
        "opener": "I noticed {company}'s website has quite a few external scripts which can slow it down.",
        "pain_points": [
            "Slow websites have 30% higher bounce rates — candidates and clients leave before seeing your offering.",
            "Google uses page speed as a ranking factor — slow sites rank lower in search results.",
            "Each second of load time reduces conversions by approximately 7%.",
        ],
        "our_solution": "Our employee portal is highly optimised — staff get fast, responsive access to HR tools regardless of connection speed.",
        "question": "Are your employees or candidates experiencing slow load times on your current HR portal?",
    },

    "no_crm": {
        "title": "No CRM Integration Detected",
        "icon": "🤝",
        "severity": "medium",
        "opener": "It doesn't look like {company} has a CRM or sales automation platform connected to the website.",
        "pain_points": [
            "Without CRM integration, leads from the website are manually tracked — causing delays and lost opportunities.",
            "Sales teams without CRM visibility have 40% lower conversion rates.",
        ],
        "our_solution": "Our Sales Intelligence module automatically captures leads, scores them, and assigns follow-up tasks — all integrated with your HR and sales workflow.",
        "question": "How does {company} currently track and follow up on sales leads or candidate enquiries?",
    },
}


def detect_opportunities(
    website_analysis: dict,
    html_content: str = "",
    company_name: str = "",
) -> list[dict]:
    """
    Detect all opportunities from website analysis + HTML content.
    Returns list of opportunity dicts with talking points.
    """
    company = company_name or "your company"
    opportunities = []

    tech_stack = website_analysis.get("techStack", [])
    is_mobile = website_analysis.get("isMobileResponsive")
    has_contact = website_analysis.get("hasContactForm")
    has_ssl = website_analysis.get("hasSSL", True)
    speed = website_analysis.get("estimatedSpeed")
    html_lower = html_content.lower()

    # ── 1. No HRMS detected ──────────────────────────────────────────────────
    has_hrms = any(signal in html_lower for signal in HRMS_SIGNALS)
    if not has_hrms:
        op = _build_opportunity("no_hrms", company, priority="critical")
        opportunities.append(op)

    # ── 2. Not mobile responsive ─────────────────────────────────────────────
    if is_mobile is False:
        op = _build_opportunity("no_mobile", company, priority="high")
        opportunities.append(op)

    # ── 3. No SSL ────────────────────────────────────────────────────────────
    if has_ssl is False:
        op = _build_opportunity("no_ssl", company, priority="high")
        opportunities.append(op)

    # ── 4. No contact form ───────────────────────────────────────────────────
    if has_contact is False:
        op = _build_opportunity("no_contact_form", company, priority="medium")
        opportunities.append(op)

    # ── 5. No analytics ──────────────────────────────────────────────────────
    analytics_tools = ["Google Analytics", "HubSpot", "Hotjar"]
    has_analytics = any(t in tech_stack for t in analytics_tools)
    if not has_analytics:
        op = _build_opportunity("no_analytics", company, priority="medium")
        opportunities.append(op)

    # ── 6. Outdated tech ─────────────────────────────────────────────────────
    outdated_found = [t for t in tech_stack if t in OUTDATED_TECH]
    if outdated_found:
        op = _build_opportunity("outdated_tech", company, priority="medium")
        op["detectedTech"] = outdated_found
        op["techNotes"] = {t: OUTDATED_TECH[t] for t in outdated_found}
        opportunities.append(op)

    # ── 7. No CRM ────────────────────────────────────────────────────────────
    if "HubSpot" not in tech_stack:
        op = _build_opportunity("no_crm", company, priority="medium")
        opportunities.append(op)

    # ── 8. Slow website ──────────────────────────────────────────────────────
    if speed == "slow":
        op = _build_opportunity("slow_website", company, priority="low")
        opportunities.append(op)

    # Sort by severity: critical > high > medium > low
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    opportunities.sort(key=lambda x: order.get(x["priority"], 4))

    return opportunities


def _build_opportunity(key: str, company: str, priority: str = None) -> dict:
    """Build a full opportunity dict from the TALKING_POINTS template."""
    template = TALKING_POINTS.get(key, {})
    comp = company or "your company"

    def fmt(s):
        return s.replace("{company}", comp) if s else s

    return {
        "key": key,
        "type": template.get("title", key),
        "icon": template.get("icon", "📌"),
        "priority": priority or template.get("severity", "medium"),
        "description": fmt(template.get("opener", "")),
        "painPoints": template.get("pain_points", []),
        "ourSolution": fmt(template.get("our_solution", "")),
        "talkingQuestion": fmt(template.get("question", "")),
    }


def generate_pitch_summary(opportunities: list[dict], company_name: str) -> str:
    """
    Generate a short pitch summary from detected opportunities.
    Returns a 3-4 sentence text for use in emails or call prep.
    """
    if not opportunities:
        return f"{company_name} has a well-maintained digital presence. Focus the conversation on growth goals and team scaling."

    company = company_name or "your prospect"
    critical = [o for o in opportunities if o["priority"] == "critical"]
    high = [o for o in opportunities if o["priority"] == "high"]
    all_types = [o["type"] for o in opportunities[:3]]

    lines = []

    if critical:
        lines.append(
            f"Key finding: {company} doesn't appear to have a dedicated HRMS — "
            "which is your strongest entry point for the conversation."
        )
    elif high:
        lines.append(
            f"Key finding: {company} has {len(high)} high-priority gap(s) including {high[0]['type']}."
        )

    if len(opportunities) >= 2:
        lines.append(
            f"In total, {len(opportunities)} opportunities were detected: "
            + ", ".join(all_types)
            + ("..." if len(opportunities) > 3 else ".")
        )

    lines.append(
        "Open the call by asking how they currently handle HR and attendance — "
        "let them identify the pain before you present the solution."
    )

    return " ".join(lines)