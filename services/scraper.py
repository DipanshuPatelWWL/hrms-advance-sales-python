"""
scraper.py  —  Web scraper + scorer pipeline
Finds companies via Google CSE (primary) or DuckDuckGo (fallback),
visits their sites, extracts emails, then scores each lead 0-100.
"""

import httpx
import asyncio
import re
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.helpers import (
    clean_company_name, is_valid_email, SKIP_EMAIL_DOMAINS,
    normalize_country, get_country_from_tld, SEARCHABLE_COUNTRIES_LIST
)
from services.scorer import score_and_analyze_lead

# ── Search credentials ───────────────────────────────────────────────────────
GOOGLE_CSE_API_KEY    = os.getenv("GOOGLE_CSE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
GOOGLE_CSE_ENGINE_ID  = os.getenv("GOOGLE_CSE_ENGINE_ID", os.getenv("GOOGLE_CX", ""))
SERPAPI_API_KEY       = os.getenv("SERPAPI_API_KEY", os.getenv("SERPAPI_KEY", ""))

# ── Request headers ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Domains to skip ──────────────────────────────────────────────────────────
SKIP_DOMAINS = [
    # Social
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
    "youtube.com", "wikipedia.org",
    # Job boards
    "indeed.com", "glassdoor.com", "reed.co.uk", "totaljobs.com",
    "cv-library.co.uk", "flexjobs.com", "monster.com", "ziprecruiter.com",
    "naukri.com", "shine.com", "timesjobs.com",
    # Review / listing sites
    "goodfirms.co", "clutch.co", "trustpilot.com", "g2.com",
    "capterra.com", "sortlist.co.uk", "upcity.com", "designrush.com",
    "expertise.com", "bark.com", "yell.com",
    "yelp.com", "yellowpages.com", "bloomberg.com", "crunchbase.com",
    "euspert.com", "peoplemanagingpeople.com", "therecruiternetwork.com",
    # Indian directories (causing your noise)
    "squareyards.com", "magicbricks.com", "99acres.com", "housing.com",
    "sulekha.com", "justdial.com", "indiamart.com", "tradeindia.com",
    "onlinebangalore.com", "yellowpages.in", "asklaila.com",
    "commonfloor.com", "proptiger.com", "homeonline.com",
    # General directories
    "hotfrog.com", "manta.com", "bizapedia.com", "dnb.com",
    "zaubacorp.com", "tofler.in", "zauba.com", "zoominfo.com",
    "builderonline.com", "contractor.com",
]

def _is_skip_domain(url: str) -> bool:
    url = url.lower()
    return any(domain in url for domain in SKIP_DOMAINS)

DIRECTORY_TITLE_KEYWORDS = [
    "top 10", "top 15", "top 20", "top 25", "top 50",
    "best companies", "best agencies", "list of", "rankings",
    "reviews", "directory", "service providers", "marketplace"
]

def _is_skip_page(url: str, title: str) -> bool:
    url_lower = url.lower()
    if any(s in url_lower for s in SKIP_DOMAINS):
        return True
    
    title_lower = title.lower()
    if any(k in title_lower for k in DIRECTORY_TITLE_KEYWORDS):
        print(f"  Skipped listicle/directory page: {title[:50]}")
        return True
    
    return False


# ── Search Implementation with Fallback ──────────────────────────────────────

async def search_with_fallback(query: str, limit: int) -> list[dict]:
    """
    Search priority:
    1. Google CSE (Primary)
    2. SerpAPI (Fallback if CSE fails or returns empty)
    """
    results = []
    
    # 1. Try Google CSE Primary
    print(f"[SEARCH_PROVIDER] Using Google CSE")
    if GOOGLE_CSE_API_KEY and GOOGLE_CSE_ENGINE_ID:
        try:
            results = await _search_google_cse(query, limit)
            if results:
                print(f"[SEARCH_PROVIDER] Google CSE returned {len(results)} results")
                return results
            else:
                print(f"[SEARCH_PROVIDER] Google CSE returned 0 results")
        except Exception as e:
            print(f"[SEARCH_PROVIDER] Google CSE failed: {e}")
    else:
        print(f"[SEARCH_PROVIDER] Google CSE credentials not set")

    # 2. Try SerpAPI Fallback
    print(f"[SEARCH_PROVIDER] Falling back to SerpAPI")
    if SERPAPI_API_KEY:
        try:
            results = await _search_google_serpapi(query, limit)
            if results:
                print(f"[SEARCH_PROVIDER] SerpAPI returned {len(results)} results")
                return results
            else:
                print(f"[SEARCH_PROVIDER] SerpAPI returned 0 results")
        except Exception as e:
            print(f"[SEARCH_PROVIDER] SerpAPI failed: {e}")
    else:
        print(f"[SEARCH_PROVIDER] SerpAPI credentials not set")

    if not results:
        print(f"[SEARCH_PROVIDER] Both providers failed or returned no results.")
    
    return []

async def _search_google_serpapi(keyword: str, limit: int) -> list[dict]:
    """Search Google via SerpAPI."""
    results = []
    if not SERPAPI_API_KEY: return []

    try:
        pages_needed = min(3, (limit * 2 + 9) // 10)
        async with httpx.AsyncClient(timeout=20) as client:
            for page in range(pages_needed):
                params = {
                    "api_key": SERPAPI_API_KEY,
                    "q":       keyword,
                    "engine":  "google",
                    "num":     10,
                    "start":   page * 10,
                    "gl":      "us",
                    "hl":      "en",
                }
                resp = await client.get("https://serpapi.com/search", params=params)
                if resp.status_code != 200:
                    print(f"  SerpAPI error {resp.status_code}: {resp.text}")
                    break

                data = resp.json()
                organic = data.get("organic_results", [])
                if not organic: break

                for item in organic:
                    url = item.get("link", "")
                    if url.startswith("http") and not _is_skip_domain(url):
                        results.append({
                            "title":   item.get("title", ""),
                            "url":     url,
                            "snippet": item.get("snippet", "")
                        })
                    if len(results) >= limit * 2: break
                
                if len(results) >= limit * 2: break
                await asyncio.sleep(0.3)

        return results[:limit * 2]
    except Exception as e:
        print(f"  SerpAPI error: {e}")
        return []

async def _search_google_cse(keyword: str, limit: int) -> list[dict]:
    """Search using Google Custom Search API."""
    results = []
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_ENGINE_ID: return []

    try:
        requests_needed = min(2, (limit * 2 + 9) // 10)
        async with httpx.AsyncClient(timeout=15) as client:
            for i in range(requests_needed):
                start_index = i * 10 + 1
                params = {
                    "key":   GOOGLE_CSE_API_KEY,
                    "cx":    GOOGLE_CSE_ENGINE_ID,
                    "q":     keyword,
                    "num":   10,
                    "start": start_index,
                }
                resp = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
                if resp.status_code != 200:
                    print(f"  Google CSE error {resp.status_code}: {resp.text}")
                    break

                data = resp.json()
                items = data.get("items", [])
                if not items: break

                for item in items:
                    url = item.get("link", "")
                    if url.startswith("http") and not _is_skip_domain(url):
                        results.append({
                            "title":   item.get("title", ""),
                            "url":     url,
                            "snippet": item.get("snippet", "")
                        })
                    if len(results) >= limit * 2: break

                if len(results) >= limit * 2: break
                await asyncio.sleep(0.5)

        return results[:limit * 2]
    except Exception as e:
        print(f"  Google CSE error: {e}")
        return []


# ── Directory URL signals ─────────────────────────────────────────────────────
DIRECTORY_URL_SIGNALS = [
    "/directory/", "/listing/", "/listings/", "/e-directories/",
    "/companies/", "/contractors/", "/builders/", "/vendors/",
    "/find-a-", "/search?", "?q=", "/profiles/", "/business/",
]

# ── Main search router ───────────────────────────────────────────────────────
async def _search_companies(keyword: str, limit: int) -> list[dict]:
    """Uses search_with_fallback and handles retry with shorter keyword."""
    results = await search_with_fallback(keyword, limit)

    # ── If still empty, retry with shorter keyword ──
    if not results:
        broader = " ".join(keyword.split()[:2])
        if broader != keyword:
            print(f"  Retrying broader search: '{broader}'")
            results = await search_with_fallback(broader, limit)

    if not results:
        return []

    # ── Filter out directory/listing URLs ──
    filtered = []
    for r in results:
        url = r.get("url", "").lower()
        if not any(sig in url for sig in DIRECTORY_URL_SIGNALS):
            filtered.append(r)
        else:
            print(f"  Skipped directory URL: {url[:60]}")

    print(f"  After directory filter: {len(filtered)}/{len(results)} results kept")
    return filtered

# ── Extract data from each page ───────────────────────────────────────────────
async def _extract_from_page(url: str, title: str, cities: list[str] = [], postal_codes: list[str] = []) -> dict | None:
    """Visit a page and extract company name, email, linkedin, country, city, postal_code."""
    email_pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )
    linkedin_pattern = re.compile(
        r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'>]+"
    )

    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # ── Company name ──
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                company_name = og_site["content"].strip()
            else:
                page_title = soup.find("title")
                company_name = clean_company_name(
                    page_title.get_text(strip=True) if page_title else title
                )

            # ── Email: mailto links first ──
            email = ""
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    candidate = href[7:].split("?")[0].strip().lower()
                    if is_valid_email(candidate):
                        domain = candidate.split("@")[-1]
                        if domain not in SKIP_EMAIL_DOMAINS:
                            email = candidate
                            break

            # ── Email: page text fallback ──
            if not email:
                for match in email_pattern.findall(html):
                    candidate = match.lower()
                    domain = candidate.split("@")[-1]
                    if (
                        is_valid_email(candidate)
                        and domain not in SKIP_EMAIL_DOMAINS
                        and "sentry" not in domain
                    ):
                        email = candidate
                        break

            # ── LinkedIn ──
            linkedin = ""
            linkedin_matches = linkedin_pattern.findall(html)
            if linkedin_matches:
                company_links = [l for l in linkedin_matches if "/company/" in l]
                linkedin = (company_links or linkedin_matches)[0]

            # ── Country Extraction (Enhanced) ──
            country = ""
            signal = "unknown"
            
            # 1. Check Schema.org JSON-LD
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        addr = item.get("address")
                        if isinstance(addr, dict):
                            c = addr.get("addressCountry")
                            if c:
                                country = str(c)
                                signal = "schema"
                                break
                        elif isinstance(addr, str) and "," in addr:
                            country = addr.split(",")[-1].strip()
                            signal = "schema"
                    if country: break
                except: pass

            # 2. Check Meta Locale
            if not country:
                og_locale = soup.find("meta", property="og:locale")
                if og_locale and og_locale.get("content"):
                    locale = og_locale["content"]
                    if "_" in locale:
                        country = locale.split("_")[-1]
                        signal = "locale"

            # 3. Check Domain TLD
            if not country:
                domain = urlparse(url).netloc.lower().replace("www.", "")
                country = get_country_from_tld(domain)
                if country: signal = "tld"

            # 4. Check Page Content / Visible Text (Dynamic using pycountry list)
            if not country:
                # Search footer/address first, then full body
                search_areas = [soup.find(["footer", "address"]), soup]
                for area in search_areas:
                    if not area: continue
                    text = area.get_text(" ", strip=True)
                    # Look for keywords with word boundaries
                    for c_keyword in SEARCHABLE_COUNTRIES_LIST:
                        # Only check keywords with length > 2 to avoid noise (except 'uk','us')
                        if len(c_keyword) <= 2 and c_keyword not in ["uk", "us"]: continue
                        
                        if re.search(rf"\b{re.escape(c_keyword)}\b", text, re.I):
                            country = c_keyword
                            signal = "page_text"
                            break
                    if country: break

            # Normalize final result
            final_country = normalize_country(country) if country else "Unknown"
            print(f"  [COUNTRY_DETECTION] Detected='{final_country}' (Source: {signal}, Raw: '{country}')")

            # ── City & Postal Code (Basic detection) ──
            city = ""
            postal_code = ""
            text_content = soup.get_text(" ", strip=True)

            # Simple check for provided cities
            for c in cities:
                if c.lower() in text_content.lower():
                    city = c
                    break
            
            # Simple check for provided postal codes
            for pc in postal_codes:
                if pc.lower() in text_content.lower():
                    postal_code = pc
                    break
            
            if not postal_code:
                # Basic regex for 5-digit (US) or 6-digit (IN) or UK-like
                pc_match = re.search(r'\b[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][ABD-HJLNP-UW-Z]{2}\b|\b\d{5}\b|\b\d{6}\b', text_content, re.I)
                if pc_match:
                    postal_code = pc_match.group()

            parsed = urlparse(url)
            clean_website = f"{parsed.scheme}://{parsed.netloc}"

            return {
                "company_name": company_name,
                "website":      clean_website,
                "email":        email,
                "linkedin":     linkedin,
                "country":      country,
                "city":         city,
                "postal_code":  postal_code,
                "source_url":   url,
            }

    except Exception as e:
        print(f"  Failed {url}: {e}")
        return None


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def find_and_score_leads(
    keyword: str,
    limit: int = 10,
    country: str = "",
    cities: list[str] = [],
    postal_codes: list[str] = [],
    domain_year_from: int = None,
    domain_year_to: int = None,
    required_techs: list[str] = [],
    genuineness_min: int = 0,
) -> list[dict]:
    """
    Main pipeline:
    1. Search Google CSE (fallback to DuckDuckGo)
    2. Visit each result page, extract data
    3. Score + analyze each lead
    4. Apply pre-save filters (country, city, postal code, domain year, tech stack, genuineness)
    Returns list of enriched, scored lead dicts.
    """
    import time
    t_start_all = time.time()

    # ── Update search query with location context ──
    search_query = keyword
    if cities:
        city_query = " OR ".join(cities[:3])
        search_query += f" {city_query}"
    if postal_codes:
        pc_query = " OR ".join(postal_codes[:3])
        search_query += f" {pc_query}"

    print(f"\n[START SEARCH] Query: '{search_query}' (limit={limit})")
    t_search_start = time.time()
    search_results = await _search_companies(search_query, limit)
    print("=" * 80)
    print("SEARCH QUERY:", search_query)
    print("SEARCH RESULTS COUNT:", len(search_results))
    for r in search_results[:10]:
        print("URL:", r.get("url"))
        print("TITLE:", r.get("title"))
        print("=" * 80)
    t_search_end = time.time()
    print(f"[END SEARCH] Found {len(search_results)} candidate URLs in {t_search_end - t_search_start:.2f}s")

    if not search_results:
        print("  No results found from any search engine")
        return []

    # Scrape pages concurrently (max 5 at a time)
    print(f"[START SCRAPING] {len(search_results)} URLs")
    t_scrape_start = time.time()
    semaphore = asyncio.Semaphore(5)

    async def scrape_one(item):
        async with semaphore:
            return await _extract_from_page(item["url"], item["title"], cities, postal_codes)

    raw_leads = await asyncio.gather(*[scrape_one(r) for r in search_results])
    raw_leads = [l for l in raw_leads if l is not None]
    print("RAW LEADS COUNT:", len(raw_leads))

    # ── Deduplicate by website ──────────────────────────────────────────────
    seen_websites = set()
    deduped = []
    for lead in raw_leads:
        website = lead.get("website", "").lower().strip()
        if website and website not in seen_websites:
            seen_websites.add(website)
            deduped.append(lead)
        elif not website:
            deduped.append(lead)
    raw_leads = deduped
    t_scrape_end = time.time()
    print(f"[END SCRAPING] Scraped {len(raw_leads)} pages successfully in {t_scrape_end - t_scrape_start:.2f}s")

    if not raw_leads:
        return []

    # Score + analyze concurrently (max 5 at a time)
    print(f"[START SCORING] {len(raw_leads[:limit])} leads")
    t_scoring_start = time.time()
    score_semaphore = asyncio.Semaphore(5)

    async def score_one(lead):
        async with score_semaphore:
            print(f"  Scoring: {lead['company_name'][:40]}")
            return await score_and_analyze_lead(lead)

    scored_leads = await asyncio.gather(*[score_one(l) for l in raw_leads[:limit]])
    print("SCORED LEADS COUNT:", len(scored_leads))
    t_scoring_end = time.time()
    print(f"[END SCORING] Scored {len(scored_leads)} leads in {t_scoring_end - t_scoring_start:.2f}s")

    scored_leads.sort(key=lambda x: x.get("score", 0), reverse=True)

    # ── Apply filters AFTER scoring ──────────────────────────────────────────
    print(f"[START FILTERING] {len(scored_leads)} leads")
    normalized_filter_country = normalize_country(country) if country else ""
    
    print(f"  Active Filters:")
    print(f"    - Country: {normalized_filter_country or 'Any'}")
    print(f"    - Cities: {cities or 'Any'}")
    print(f"    - Postal Codes: {postal_codes or 'Any'}")
    print(f"    - Domain Year: {domain_year_from or 'Any'} to {domain_year_to or 'Any'}")
    print(f"    - Tech Stack: {required_techs or 'Any'}")
    print(f"    - Genuineness Min: {genuineness_min}")

    t_filtering_start = time.time()
    final = []
    for lead in scored_leads:
        company = lead.get("company_name", "Unknown")
        rejected = False
        reason = ""

        # Country filter
        if normalized_filter_country:
            raw_detected = lead.get("country") or "Unknown"
            normalized_detected = normalize_country(raw_detected)
            
            # If we don't know the country, we don't reject it (be lenient)
            if normalized_detected != "Unknown" and normalized_detected.lower() != normalized_filter_country.lower():
                reason = f"Country mismatch: Raw='{raw_detected}', Normalized='{normalized_detected}', Expected='{normalized_filter_country}'"
                rejected = True
            else:
                print(f"  Country Match/Pass: '{normalized_detected}' vs '{normalized_filter_country}'")

        # City filter
        if not rejected and cities:
            lead_city = (lead.get("city") or "").lower().strip()
            if lead_city:
                cities_lower = [c.lower().strip() for c in cities]
                if lead_city not in cities_lower:
                    reason = f"City mismatch: Detected='{lead_city}', Expected one of {cities_lower}"
                    rejected = True
        
        # Postal Code filter
        if not rejected and postal_codes:
            lead_pc = (lead.get("postal_code") or "").lower().strip()
            if lead_pc:
                pcs_lower = [p.lower().strip() for p in postal_codes]
                if lead_pc not in pcs_lower:
                    reason = f"Postal code mismatch: Detected='{lead_pc}', Expected one of {pcs_lower}"
                    rejected = True

        # Domain year range filter
        if not rejected:
            year = (lead.get("websiteAnalysis") or {}).get("domainCreatedYear")
            if year is not None:
                if domain_year_from and year < domain_year_from:
                    reason = f"Year too old: {year} < {domain_year_from}"
                    rejected = True
                elif domain_year_to and year > domain_year_to:
                    reason = f"Year too new: {year} > {domain_year_to}"
                    rejected = True

        # Tech stack filter
        if not rejected and required_techs:
            lead_techs = (lead.get("websiteAnalysis") or {}).get("techStack", [])
            lead_techs_lower = [t.lower() for t in lead_techs]
            has_any = any(rt.lower() in lead_techs_lower for rt in required_techs)
            if not has_any:
                reason = f"No matching tech stack. Lead has: {lead_techs}"
                rejected = True

        # Genuineness filter
        if not rejected and genuineness_min > 0:
            g_score = lead.get("genuinenessScore") or 0
            if g_score < genuineness_min:
                reason = f"Genuineness too low: {g_score} < {genuineness_min}"
                rejected = True

        if rejected:
            print(f"  Rejected Lead:")
            print(f"    Company: {company}")
            print(f"    Reason: {reason}")
        else:
            final.append(lead)

    t_filtering_end = time.time()
    print(f"[END FILTERING] {len(final)}/{len(scored_leads)} leads kept in {t_filtering_end - t_filtering_start:.2f}s")
    
    t_end_all = time.time()
    print(f"[RETURN RESPONSE] Total time: {t_end_all - t_start_all:.2f}s")
    print("FINAL LEADS COUNT:", len(final))

    for lead in final[:5]:
     print(
        "LEAD:",
        lead.get("company_name"),
        "|",
        lead.get("website"),
        "|",
        lead.get("email")
    )

    return final