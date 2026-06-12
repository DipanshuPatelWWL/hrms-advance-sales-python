"""
foursquare_scraper.py — OpenStreetMap (Overpass API) lead finder
Free, no API key needed.
Returns: business name, phone, website, address, country
"""

import httpx
import asyncio
import re
import random
import math
import sys
from bs4 import BeautifulSoup
from services.scorer import score_and_analyze_lead
from utils.helpers import is_valid_email, SKIP_EMAIL_DOMAINS, safe_print
from utils.playwright_helper import get_rendered_html

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

HEADERS = {
    "User-Agent": "HRMS-LeadEngine/1.0",
    "Accept": "application/json",
}

COUNTRY_CITY_MAP = {
    "usa": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
    "united states": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
    "uk": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
    "united kingdom": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
    "canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "india": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
    "australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
}

SEARCH_ALIASES = {
    "Recruitment Agency": ["recruitment", "staffing", "employment", "talent", "headhunter"],
    "Staffing Agency": ["staffing", "recruitment", "talent", "employment"],
    "Logistics Company": ["logistics", "freight", "transport", "shipping", "warehouse"],
    "IT Company": ["software", "technology", "IT", "digital", "development"],
}

GEO_CACHE = {}


async def _geocode_location(location: str) -> dict | None:
    """Convert location string to bounding box using Nominatim."""
    if not location:
        return None
    
    loc_key = location.lower().strip()
    if loc_key in GEO_CACHE:
        return GEO_CACHE[loc_key]

    try:
        await asyncio.sleep(1.1)
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(NOMINATIM_URL, params={"q": location, "format": "json", "limit": 1})
            data = resp.json()
            if data:
                bb = data[0].get("boundingbox", [])
                if len(bb) == 4:
                    res = {
                        "south": bb[0], "north": bb[1],
                        "west":  bb[2], "east":  bb[3],
                        "display": data[0].get("display_name", location),
                    }
                    GEO_CACHE[loc_key] = res
                    return res
    except Exception as e:
        safe_print(f"Geocode error for {location}: {e}")
    return None


async def _search_overpass(keyword: str, limit: int, location: str = "", search_mode: str = "fast") -> list[dict]:
    """Search OpenStreetMap via Overpass API."""

    search_terms = SEARCH_ALIASES.get(keyword, [keyword])
    keyword_pattern = "|".join(search_terms)

    loc_lower = location.lower().strip()
    if loc_lower in COUNTRY_CITY_MAP:
        safe_print(f"Country detected: {location}. Mode: {search_mode}. Splitting into city searches...")

        all_results = []
        seen_items = set()
        cities = COUNTRY_CITY_MAP[loc_lower]

        if search_mode == "distributed":
            quota = max(3, math.ceil(limit / len(cities)))
            safe_print(f"Distributed mode: Quota of {quota} leads per city.")
            
            for city in cities:
                try:
                    city_results = await _search_overpass(keyword, quota * 2, city, search_mode="fast")
                    if not city_results: continue
                    
                    for r in city_results[:quota]:
                        web = r.get("website", "")
                        key = f"web:{web.lower()}" if web else f"name:{r.get('company_name', '').strip().lower()}"
                        if key not in seen_items:
                            all_results.append(r)
                            seen_items.add(key)
                except Exception as e:
                    safe_print(f"City search failed for {city}: {e}")
                    continue
        else:
            for city in cities:
                if len(all_results) >= limit * 2:
                    safe_print(f"Buffer reached ({len(all_results)}). Skipping remaining cities.")
                    break
                try:
                    city_results = await _search_overpass(keyword, limit, city, search_mode="fast")
                    if not city_results: continue
                    for r in city_results:
                        web = r.get("website", "")
                        key = f"web:{web.lower()}" if web else f"name:{r.get('company_name', '').strip().lower()}"
                        if key not in seen_items:
                            all_results.append(r)
                            seen_items.add(key)
                except Exception as e:
                    safe_print(f"City search failed for {city}: {e}")
                    continue
        return all_results

    if location:
        bbox_data = await _geocode_location(location)
        if not bbox_data:
            safe_print(f"Geocoding failed for '{location}'. Skipping.")
            return []
        
        try:
            lat_diff = abs(float(bbox_data["north"]) - float(bbox_data["south"]))
            lon_diff = abs(float(bbox_data["east"])  - float(bbox_data["west"]))
            if lat_diff > 8 or lon_diff > 8:
                safe_print(f"Location '{location}' is too broad. Skipping.")
                return []
        except (ValueError, TypeError):
            return []

        bbox = f"{bbox_data['south']},{bbox_data['west']},{bbox_data['north']},{bbox_data['east']}"
        area_filter = f"({bbox})"
    else:
        area_filter = ""

    query = f'[out:json][timeout:90];(node["name"~"{keyword_pattern}",i]{area_filter};way["name"~"{keyword_pattern}",i]{area_filter};node["office"~"{keyword_pattern}",i]{area_filter};way["office"~"{keyword_pattern}",i]{area_filter};node["company"~"{keyword_pattern}",i]{area_filter};);out body {limit * 3};' if area_filter else f'[out:json][timeout:90];(node["name"~"{keyword_pattern}",i]["website"](if: count_tags() > 3);way["name"~"{keyword_pattern}",i]["website"](if: count_tags() > 3););out body {limit * 2};'

    results = []
    total_attempts = 4
    retry_delays = [5, 10, 20]
    current_endpoint_idx = 0

    for attempt in range(total_attempts):
        endpoint = OVERPASS_ENDPOINTS[current_endpoint_idx]
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(1, 2))
            async with httpx.AsyncClient(timeout=100, headers=HEADERS) as client:
                resp = await client.post(endpoint, data={"data": query})
                duration = asyncio.get_event_loop().time() - start_time
                if (resp.status_code == 429 or 500 <= resp.status_code <= 504) and attempt < total_attempts - 1:
                    current_endpoint_idx = (current_endpoint_idx + 1) % len(OVERPASS_ENDPOINTS)
                    safe_print(f"Overpass {resp.status_code} Attempt {attempt + 1}/{total_attempts} Duration: {duration:.2f}s")
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                resp.raise_for_status()
                data = resp.json()
                safe_print(f"Overpass success Duration: {duration:.2f}s Elements: {len(data.get('elements', []))}")

            for element in data.get("elements", []):
                tags = element.get("tags", {})
                name = tags.get("name", "")
                if not name: continue
                website = tags.get("website", "") or tags.get("contact:website", "")
                if website and not website.startswith("http"): website = "https://" + website

                results.append({
                    "company_name": str(name),
                    "phone":        str(tags.get("phone", "") or tags.get("contact:phone", "")),
                    "website":      str(website),
                    "address":      str(", ".join(p for p in [tags.get("addr:city", ""), tags.get("addr:street", ""), tags.get("addr:housenumber", "")] if p)),
                    "country":      str(tags.get("addr:country", "")),
                    "category":     str(tags.get("office") or tags.get("shop") or tags.get("amenity") or "business"),
                    "email":        str(tags.get("email", "") or tags.get("contact:email", "")),
                    "linkedin":     "",
                    "source":       "openstreetmap",
                })
                if len(results) >= limit * 2: break
            break
        except Exception as e:
            if attempt == total_attempts - 1:
                safe_print(f"Overpass final failure: {e}")
                raise
            current_endpoint_idx = (current_endpoint_idx + 1) % len(OVERPASS_ENDPOINTS)
            await asyncio.sleep(retry_delays[attempt])
    return results


async def _enrich_with_email(lead: dict) -> dict:
    """Visit the business website to extract email + linkedin."""
    website = lead.get("website", "")
    if not website or not website.startswith("http") or lead.get("email"): return lead
    try:
        html = await get_rendered_html(website)
        if not html: return lead
        soup = BeautifulSoup(html, "html.parser")
        email = ""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                candidate = href[7:].split("?")[0].strip().lower()
                if is_valid_email(candidate):
                    email = candidate
                    break
        if not email:
            matches = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
            if matches: email = matches[0].lower()
        matches = re.findall(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'>]+", html)
        if matches: lead["linkedin"] = str(matches[0])
        lead["email"] = str(email)
    except Exception: pass
    return lead


async def find_leads_foursquare(keyword: str, limit: int = 10, location: str = "", enrich_email: bool = True, search_mode: str = "fast") -> list[dict]:
    """Main pipeline — uses OpenStreetMap."""
    import time
    t_start = time.time()
    
    safe_print(f"OSM search: '{keyword}' location='{location}' (limit={limit}, mode={search_mode})")
    
    t_overpass_start = time.time()
    raw = await _search_overpass(keyword, limit, location, search_mode=search_mode)
    t_overpass_end = time.time()
    
    safe_print(f"Found {len(raw)} businesses from OpenStreetMap (Time: {t_overpass_end - t_overpass_start:.2f}s)")
    if not raw: return []

    if enrich_email:
        safe_print(f"Starting Playwright enrichment for {len(raw)} leads...")
        t_enrich_start = time.time()
        semaphore = asyncio.Semaphore(5)
        async def enrich_one(lead):
            async with semaphore: return await _enrich_with_email(lead)
        raw = list(await asyncio.gather(*[enrich_one(r) for r in raw]))
        t_enrich_end = time.time()
        safe_print(f"Email enrichment complete (Time: {t_enrich_end - t_enrich_start:.2f}s)")

    safe_print(f"Starting Scoring phase for {len(raw[:limit])} leads (Concurrency: 3)...")
    t_scoring_start = time.time()
    score_sem = asyncio.Semaphore(3)
    async def score_one(lead):
        async with score_sem:
            t_s1 = time.time()
            safe_print(f"Scoring: {lead.get('company_name', 'Unknown')[:40]}")
            scored = await score_and_analyze_lead(lead)
            scored.update({
                "phone": str(lead.get("phone", "")),
                "address": str(lead.get("address", "")),
                "category": str(lead.get("category", "")),
                "source": "openstreetmap"
            })
            t_s2 = time.time()
            safe_print(f"  - Lead scored in {t_s2 - t_s1:.2f}s")
            return scored

    scored_leads = list(await asyncio.gather(*[score_one(r) for r in raw[:limit]]))
    t_scoring_end = time.time()
    
    scored_leads.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    t_total = time.time() - t_start
    safe_print(f"Pipeline complete in {t_total:.2f}s. Avg scoring: {(t_scoring_end - t_scoring_start)/max(1, len(scored_leads)):.2f}s/lead")
    return scored_leads
