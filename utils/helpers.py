import re
from urllib.parse import urlparse


import sys

def safe_print(*args, **kwargs):
    """Print to console with fallbacks for UnicodeEncodeError (Windows)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            # Try forcing UTF-8 write to buffer
            msg = " ".join(str(arg) for arg in args)
            sys.stdout.buffer.write((msg + "\n").encode("utf-8"))
        except:
            # Fallback to ascii with replacement
            encoding = sys.stdout.encoding or 'ascii'
            clean = [str(arg).encode(encoding, errors='replace').decode(encoding) for arg in args]
            print(*clean, **kwargs)

# ─── Email extraction ─────────────────────────────────────────────────────────
# Matches standard emails, avoids image/asset filenames
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Domains to skip — these are not real contact emails
SKIP_EMAIL_DOMAINS = {
    "example.com", "test.com", "domain.com", "email.com",
    "yourdomain.com", "wixpress.com", "squarespace.com",
    "wordpress.com", "shopify.com", "amazonaws.com", "googletagmanager.com",
    "schema.org", "w3.org", "facebook.com", "twitter.com", "instagram.com",
    # ← ADD THESE
    "sentry.io", "sentry.com",           # error tracking emails
    "intercom.io",                        # chat widget emails
    "hubspot.com", "mailchimp.com",       # marketing tools
    "zendesk.com", "freshdesk.com",       # support tools
    "cloudflare.com", "fastly.com",       # CDN
    "segment.com", "mixpanel.com",        # analytics
    "doubleclick.net", "googlesyndication.com",
}


def extract_emails_from_html(html: str) -> list[str]:
    """Extract unique, valid contact emails from raw HTML."""
    found = EMAIL_REGEX.findall(html)
    clean = []
    seen = set()
    for email in found:
        email = email.lower().strip()
        domain = email.split("@")[-1]
        if domain in SKIP_EMAIL_DOMAINS:
            continue
   # Skip image/asset false positives like "icon@2x.png"
        if any(email.endswith(ext) for ext in [".png", ".jpg", ".gif", ".svg", ".webp"]):
            continue
        # Skip obvious false positives by keyword
        if any(bad in email for bad in ["scam", "spam", "noreply", "no-reply", "2x-", "@2x", "unsubscribe"]):
            continue
        if email not in seen:
            seen.add(email)
            clean.append(email)
    return clean[:3]  # return top 3 emails max


# ─── URL helpers ─────────────────────────────────────────────────────────────
def clean_url(url: str) -> str:
    """Ensure URL has https:// prefix."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def get_domain(url: str) -> str:
    """Extract domain from URL. e.g. https://abc.co.uk/about → abc.co.uk"""
    try:
        parsed = urlparse(clean_url(url))
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception:
        return url


def is_valid_url(url: str) -> bool:
    """Check if URL looks real enough to visit."""
    if not url or len(url) < 6:
        return False
    try:
        parsed = urlparse(clean_url(url))
        return bool(parsed.netloc) and parsed.scheme in ("http", "https")
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    """Basic email validation."""
    if not email or "@" not in email:
        return False
    pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    return bool(pattern.match(email.strip())) and len(email) < 80


# ─── Country Normalization ──────────────────────────────────────────────────
import pycountry

COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.a": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "great britain": "United Kingdom",
    "u.k": "United Kingdom",
    "u.k.": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "ind": "India",
    "aus": "Australia",
    "can": "Canada",
    "deu": "Germany",
    "de": "Germany",
    "fr": "France",
    "fra": "France",
    "it": "Italy",
    "ita": "Italy",
    "esp": "Spain",
    "es": "Spain",
    "nl": "Netherlands",
    "nld": "Netherlands",
    "nz": "New Zealand",
    "nzl": "New Zealand",
    "rsa": "South Africa",
    "sg": "Singapore",
    "sgp": "Singapore",
    "hk": "Hong Kong",
    "hkg": "Hong Kong",
    "ie": "Ireland",
    "irl": "Ireland",
}

def is_valid_country(name: str) -> bool:
    """Check if a string resolves to a real country using pycountry."""
    if not name or name.lower() in ["unknown", "none", "null"]:
        return False
    try:
        # Check by name
        if pycountry.countries.get(name=name): return True
        # Check by alpha_2 or alpha_3
        if len(name) in [2, 3] and (pycountry.countries.get(alpha_2=name.upper()) or pycountry.countries.get(alpha_3=name.upper())):
            return True
        # Check fuzzy
        results = pycountry.countries.search_fuzzy(name)
        return len(results) > 0
    except:
        return False

# Generate a list of common searchable names for all countries
_SEARCHABLE_COUNTRIES = []
try:
    for c in pycountry.countries:
        names = [c.name]
        if hasattr(c, 'common_name'): names.append(c.common_name)
        if hasattr(c, 'official_name'): names.append(c.official_name)
        _SEARCHABLE_COUNTRIES.extend([n.lower() for n in names])
    
    # ── CRITICAL: Remove short abbreviations from text scanning to avoid "us", "in", "it" ──
    # These will still work in normalize_country() for schema/TLD signals
    SEARCHABLE_COUNTRIES_LIST = sorted([
        n for n in list(set(_SEARCHABLE_COUNTRIES)) 
        if len(n) > 3 or n in ["uae", "usa"] # keep specific valid abbreviations > 2 chars
    ], key=len, reverse=True)
except:
    SEARCHABLE_COUNTRIES_LIST = ["united states", "united kingdom", "india", "australia", "canada", "germany", "france", "albania", "united arab emirates"]

def normalize_country(name: str) -> str:
    """Standardize country names using aliases and pycountry."""
    if not name:
        return "Unknown"
    
    clean_name = name.strip().lower()
    
    # 1. Check Aliases
    if clean_name in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[clean_name]
    
    # 2. Try pycountry lookup
    try:
        # Search by name
        country = pycountry.countries.get(name=name)
        if country: return country.name
        
        # Search by fuzzy name
        results = pycountry.countries.search_fuzzy(name)
        if results: return results[0].name
        
        # Search by alpha_2 or alpha_3
        if len(clean_name) in [2, 3]:
            country = pycountry.countries.get(alpha_2=clean_name.upper()) or \
                      pycountry.countries.get(alpha_3=clean_name.upper())
            if country: return country.name
    except:
        pass
    
    # Fallback to Title Case if not found
    return name.title()

TLD_COUNTRY_MAP = {
    "uk": "United Kingdom",
    "co.uk": "United Kingdom",
    "org.uk": "United Kingdom",
    "au": "Australia",
    "com.au": "Australia",
    "ca": "Canada",
    "in": "India",
    "co.in": "India",
    "de": "Germany",
    "fr": "France",
    "it": "Italy",
    "es": "Spain",
    "nl": "Netherlands",
    "nz": "New Zealand",
    "ie": "Ireland",
    "za": "South Africa",
    "sg": "Singapore",
    "hk": "Hong Kong",
    "al": "Albania",
    "albania": "Albania",
    "us": "United States",
    "com": "", # Generic, cannot infer
    "org": "",
    "net": "",
    "io": "",
}

def get_country_from_tld(domain: str) -> str:
    """Infer country from domain TLD."""
    if not domain: return ""
    parts = domain.lower().split(".")
    # Check 2nd-level TLD first (e.g. co.uk)
    if len(parts) >= 2:
        tld_2 = ".".join(parts[-2:])
        if tld_2 in TLD_COUNTRY_MAP:
            return TLD_COUNTRY_MAP[tld_2]
    
    # Check top-level TLD
    tld_1 = parts[-1]
    if tld_1 in TLD_COUNTRY_MAP:
        return TLD_COUNTRY_MAP[tld_1]
    
    return ""

# ─── Company name cleaner ─────────────────────────────────────────────────────
def clean_company_name(name: str) -> str:
    """Remove common suffixes and extra whitespace."""
    if not name:
        return "Unknown"
    name = name.strip()
    # Remove trailing descriptors often in search titles
    suffixes = [
        " - Home", " | Home", " – Home",
        " - Official Site", " | Official Site",
        " - LinkedIn", " | LinkedIn",
        " - Contact", " | Contact",
    ]
    for s in suffixes:
        if name.endswith(s):
            name = name[: -len(s)]
    return name.strip()


# ─── Genuineness Score ────────────────────────────────────────────────────────
FREE_DOMAIN_SIGNALS = [
    "wix.com", "wixsite.com", "wordpress.com", "weebly.com",
    "squarespace.com", "webflow.io", "blogspot.com", "tumblr.com",
    "godaddysites.com", "site123.me", "jimdo.com", "yolasite.com",
]

GENERIC_EMAIL_PREFIXES = [
    "noreply", "no-reply", "donotreply", "info", "contact",
    "hello", "support", "admin", "help", "team", "mail",
    "sales", "marketing", "enquiries", "enquiry",
]

def calculate_genuineness(lead: dict, domain_age_years: float = None) -> dict:
    """
    Score a lead's genuineness 0–100 based on multiple signals.
    Returns { score, label, signals }
    """
    score = 0
    signals = {}

    # ── Has real email (not noreply/info) — 20 pts ──
    email = (lead.get("email", "") or "").lower()
    if email and "@" in email:
        prefix = email.split("@")[0]
        is_generic = any(g in prefix for g in GENERIC_EMAIL_PREFIXES)
        if not is_generic:
            score += 20
            signals["realEmail"] = True
        else:
            signals["realEmail"] = False
    else:
        signals["realEmail"] = False

    # ── Has LinkedIn company page — 20 pts ──
    linkedin = (lead.get("linkedin", "") or "").lower()
    if "linkedin.com/company/" in linkedin:
        score += 20
        signals["hasLinkedIn"] = True
    else:
        signals["hasLinkedIn"] = False

    # ── Domain age > 2 years — 20 pts ──
    if domain_age_years is not None:
        if domain_age_years >= 2:
            score += 20
            signals["domainMature"] = True
        else:
            signals["domainMature"] = False
        signals["domainAgeYears"] = round(domain_age_years, 1)
    else:
        signals["domainMature"] = None
        signals["domainAgeYears"] = None

    # ── Has phone number — 15 pts ──
    phone = (lead.get("phone", "") or "").strip()
    if phone and len(phone) >= 7:
        score += 15
        signals["hasPhone"] = True
    else:
        signals["hasPhone"] = False

    # ── HTTPS website — 10 pts ──
    website = (lead.get("website", "") or "").lower()
    if website.startswith("https://"):
        score += 10
        signals["hasHttps"] = True
    else:
        signals["hasHttps"] = False

    # ── Not a free domain builder — 15 pts ──
    is_free_domain = any(s in website for s in FREE_DOMAIN_SIGNALS)
    if website and not is_free_domain:
        score += 15
        signals["ownDomain"] = True
    else:
        signals["ownDomain"] = False

    score = min(score, 100)

    if score >= 80:
        label = "genuine"
    elif score >= 50:
        label = "unverified"
    else:
        label = "suspicious"

    return {
        "genuinenessScore": score,
        "genuinenessLabel": label,
        "genuinenessSignals": signals,
    }





# ─── Technology Stack Detector ────────────────────────────────────────────────
TECH_FINGERPRINTS = [
    # CMS
    ("WordPress",        ["wp-content", "wp-includes", "wp-json", "/wp-login"]),
    ("Shopify",          ["shopify.com", "cdn.shopify", "Shopify.theme", "myshopify.com"]),
    ("Wix",              ["wix.com", "wixstatic.com", "X-Wix-"]),
    ("Squarespace",      ["squarespace.com", "static.squarespace", "squarespace-cdn"]),
    ("Webflow",          ["webflow.io", "webflow.com", ".w-"]),
    ("Drupal",           ["drupal.js", "drupal.min.js", "/sites/default/files", "Drupal.settings"]),
    ("Joomla",           ["/components/com_", "Joomla!", "/media/jui/"]),
    ("Ghost",            ["ghost.io", "content/themes/casper", "/ghost/"]),
    ("Weebly",           ["weebly.com", "weeblycloud.com"]),
    # JS Frameworks
    ("Next.js",          ["_next/static", "__NEXT_DATA__", "/_next/chunks"]),
    ("Nuxt.js",          ["__NUXT__", "_nuxt/", "nuxt.js"]),
    ("React",            ["react.development.js", "react.production.min.js", "reactDOM", "__react"]),
    ("Vue.js",           ["vue.min.js", "vue.runtime", "__vue__", "v-app"]),
    ("Angular",          ["ng-version", "angular.min.js", "ng-app", "/main.js"]),
    ("Svelte",           ["svelte", "__svelte"]),
    ("Gatsby",           ["gatsby", "___gatsby"]),
    ("Ember.js",         ["ember.js", "ember.min.js", "Ember.Application"]),
    # CRM / Marketing
    ("HubSpot",          ["hubspot.com", "hs-scripts.com", "hubspot", "hsforms"]),
    ("Salesforce",       ["salesforce.com", "force.com", "pardot.com", "exacttarget"]),
    ("Zoho",             ["zoho.com", "zohopublic.com", "zohocrm"]),
    ("Pipedrive",        ["pipedrive.com"]),
    ("Intercom",         ["intercom.io", "widget.intercom.io", "intercomSettings"]),
    ("Zendesk",          ["zendesk.com", "zdassets.com", "zopim.com"]),
    ("Freshdesk",        ["freshdesk.com", "freshchat.com", "freshworks.com"]),
    ("Drift",            ["drift.com", "js.driftt.com"]),
    ("Crisp",            ["crisp.chat", "client.crisp.chat"]),
    # Analytics
    ("Google Analytics", ["gtag(", "google-analytics.com", "googletagmanager.com", "ga('create"]),
    ("Hotjar",           ["hotjar.com", "hj('create", "hjSiteSettings"]),
    ("Mixpanel",         ["mixpanel.com", "mixpanel.init"]),
    ("Segment",          ["segment.com", "analytics.js", "cdn.segment"]),
    ("Clarity",          ["clarity.ms", "Microsoft Clarity"]),
    # E-commerce
    ("WooCommerce",      ["woocommerce", "wc-blocks", "wc_cart_fragments"]),
    ("Magento",          ["Magento", "mage/", "requirejs/require.js"]),
    ("BigCommerce",      ["bigcommerce.com", "bc-sf-filter"]),
    ("PrestaShop",       ["prestashop", "presta_shop"]),
    # Hosting / CDN
    ("Cloudflare",       ["cloudflare.com", "__cfduid", "cf-ray"]),
    ("AWS",              ["amazonaws.com", "cloudfront.net"]),
    ("Vercel",           ["vercel.app", "_vercel", "x-vercel"]),
    ("Netlify",          ["netlify.app", "netlify.com"]),
    # Payment
    ("Stripe",           ["stripe.com", "js.stripe.com", "stripe.js"]),
    ("PayPal",           ["paypal.com", "paypalobjects.com"]),
    # Misc
    ("Bootstrap",        ["bootstrap.min.css", "bootstrap.css", "bootstrap.bundle"]),
    ("Tailwind",         ["tailwind.css", "tailwindcss"]),
    ("jQuery",           ["jquery.min.js", "jquery-", "jQuery.fn"]),
    ("Font Awesome",     ["fontawesome", "font-awesome"]),
    ("Typeform",         ["typeform.com", "embed.typeform"]),
    ("Calendly",         ["calendly.com", "assets.calendly"]),
    ("Mailchimp",        ["mailchimp.com", "chimpstatic.com", "mc.js"]),
]


def detect_tech_stack(html: str) -> list[str]:
    """
    Detect technologies from raw HTML using fingerprint matching.
    Returns list of detected technology names (max 15).
    """
    if not html:
        return []

    html_lower = html.lower()
    detected = []

    for tech_name, fingerprints in TECH_FINGERPRINTS:
        for fp in fingerprints:
            if fp.lower() in html_lower:
                detected.append(tech_name)
                break  # One match per tech is enough

    return detected[:15]


# ─── LinkedIn URL extractor ───────────────────────────────────────────────────
LINKEDIN_REGEX = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9\-_%]+"
)


def extract_linkedin(html: str) -> str:
    """Find first LinkedIn company/profile URL in page HTML."""
    match = LINKEDIN_REGEX.search(html)
    return match.group(0) if match else ""