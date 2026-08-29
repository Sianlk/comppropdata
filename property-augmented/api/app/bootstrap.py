from __future__ import annotations

import csv
import io
import os
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .full_stack import app
from . import main as core

GOOGLE_TRENDS_GEO = os.getenv("GOOGLE_TRENDS_GEO", "GB")
GOOGLE_TRENDS_RSS_URL = os.getenv("GOOGLE_TRENDS_RSS_URL", "https://trends.google.com/trending/rss")
GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN = os.getenv("GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN", "")
GOOGLE_SEARCH_CONSOLE_SITE_URL = os.getenv("GOOGLE_SEARCH_CONSOLE_SITE_URL", "")
SEMRUSH_API_KEY = os.getenv("SEMRUSH_API_KEY", "")
SEMRUSH_API_URL = os.getenv("SEMRUSH_API_URL", "https://api.semrush.com/")


class TrendsRequest(BaseModel):
    geo: str = "GB"
    limit: int = Field(25, ge=1, le=100)


class SearchConsoleRequest(BaseModel):
    site_url: str = ""
    start_date: str = ""
    end_date: str = ""
    dimensions: list[str] = Field(default_factory=lambda: ["query", "page"])
    row_limit: int = Field(250, ge=1, le=25000)


class KeywordMetricRequest(BaseModel):
    keywords: list[str]
    database: str = "uk"


def _provider_status() -> dict[str, Any]:
    return {
        "api": True,
        "ai": bool(core.OPENAI_API_KEY),
        "database": bool(os.getenv("DATABASE_URL", "")),
        "stripe": bool(os.getenv("STRIPE_SECRET_KEY", "")),
        "companies_house": bool(core.COMPANIES_HOUSE_API_KEY),
        "epc": bool(core.EPC_API_URL),
        "google_trends": True,
        "google_search_console": bool(GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN and GOOGLE_SEARCH_CONSOLE_SITE_URL),
        "semrush": bool(SEMRUSH_API_KEY),
    }


@app.get("/api/v1/system/status")
def system_status():
    return {
        "status": "healthy",
        "service": core.APP,
        "version": core.VERSION,
        "providers": _provider_status(),
        "principles": [
            "Live data must retain source and retrieval context.",
            "Missing evidence is not established.",
            "AI output is working material until human review.",
            "Professional and statutory judgement remains with the appropriate person or authority.",
        ],
    }


# Stable aliases used by the independent frontend. The older endpoints remain available.
@app.post("/api/v1/ai/analyse")
async def ai_analyse_alias(r: core.Analysis):
    return await core.assist(r)


@app.post("/api/v1/calculators/residual")
def residual_alias(r: core.Residual):
    return core.residual(r)


@app.post("/api/v1/quotes/compare")
async def quote_alias(r: core.Quotes):
    return await core.quotes(r)


@app.post("/api/v1/seo/strategy")
async def seo_alias(r: core.SEO):
    return await core.seo(r)


@app.get("/api/v1/data/companies-house/search")
async def companies_house_search(q: str):
    if not core.COMPANIES_HOUSE_API_KEY:
        raise HTTPException(503, "Companies House is not configured")
    url = "https://api.company-information.service.gov.uk/search/companies"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params={"q": q, "items_per_page": 50}, auth=(core.COMPANIES_HOUSE_API_KEY, ""))
        response.raise_for_status()
        data = response.json()
    return {
        "items": data.get("items", []),
        "source": core.src("Companies House API", url, "Verify company status and filings in the authoritative Companies House record."),
    }


@app.post("/api/v1/seo/trending-now")
async def trending_now(r: TrendsRequest):
    url = GOOGLE_TRENDS_RSS_URL
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, params={"geo": r.geo or GOOGLE_TRENDS_GEO}, headers={"User-Agent": "PropertyDevelopmentAugmented/2.0"})
            response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item")[: r.limit]:
            row: dict[str, Any] = {
                "title": (item.findtext("title") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
            }
            for child in list(item):
                tag = child.tag.split("}")[-1]
                if tag in {"approx_traffic", "picture", "picture_source"}:
                    row[tag] = (child.text or "").strip()
            if row["title"]:
                items.append(row)
        return {
            "geo": r.geo,
            "items": items,
            "source": core.src("Google Trends - Trending now", f"https://trends.google.com/trending?geo={quote(r.geo)}", "Trending searches are not keyword demand forecasts and should not be treated as SEO search volume."),
        }
    except Exception as exc:
        raise HTTPException(502, f"Google Trends feed unavailable: {exc}") from exc


@app.post("/api/v1/seo/search-console")
async def search_console(r: SearchConsoleRequest):
    token = GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN
    site_url = r.site_url or GOOGLE_SEARCH_CONSOLE_SITE_URL
    if not token or not site_url:
        raise HTTPException(503, "Google Search Console is not configured")
    end = r.end_date or date.today().isoformat()
    start = r.start_date or (date.today() - timedelta(days=28)).isoformat()
    url = f"https://www.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query"
    payload = {"startDate": start, "endDate": end, "dimensions": r.dimensions, "rowLimit": r.row_limit}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
        if response.status_code >= 400:
            raise HTTPException(502, f"Search Console API error {response.status_code}: {response.text[:500]}")
        data = response.json()
    return {
        "site_url": site_url,
        "date_range": {"start": start, "end": end},
        "rows": data.get("rows", []),
        "response_aggregation_type": data.get("responseAggregationType"),
        "source": core.src("Google Search Console Search Analytics", "https://developers.google.com/webmaster-tools/v1/searchanalytics/query", "First-party search performance for an authorised property; data is not a promise of future ranking."),
    }


async def _semrush_phrase(keyword: str, database: str) -> dict[str, Any]:
    if not SEMRUSH_API_KEY:
        return {"keyword": keyword, "configured": False, "volume": None, "cpc": None, "competition": None, "results": None, "trend": None}
    params = {
        "type": "phrase_this",
        "key": SEMRUSH_API_KEY,
        "phrase": keyword,
        "database": database,
        "export_columns": "Ph,Nq,Cp,Co,Nr,Td",
        "display_limit": 1,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(SEMRUSH_API_URL, params=params)
        if response.status_code >= 400:
            return {"keyword": keyword, "configured": True, "error": f"HTTP {response.status_code}"}
        text = response.text.strip()
    if not text or text.startswith("ERROR"):
        return {"keyword": keyword, "configured": True, "error": text or "No data"}
    rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))
    if not rows:
        return {"keyword": keyword, "configured": True, "volume": None}
    row = rows[0]
    return {
        "keyword": keyword,
        "configured": True,
        "volume": row.get("Search Volume") or row.get("Nq"),
        "cpc": row.get("CPC") or row.get("Cp"),
        "competition": row.get("Competition") or row.get("Co"),
        "results": row.get("Number of Results") or row.get("Nr"),
        "trend": row.get("Trends") or row.get("Td"),
    }


@app.post("/api/v1/seo/measured-keywords")
async def measured_keywords(r: KeywordMetricRequest):
    metrics = []
    for keyword in list(dict.fromkeys(k.strip() for k in r.keywords if k.strip()))[:50]:
        metrics.append(await _semrush_phrase(keyword, r.database))
    return {
        "database": r.database,
        "metrics": metrics,
        "provider": "Semrush" if SEMRUSH_API_KEY else "not configured",
        "note": "Only provider-returned metrics are surfaced. No volume or competition values are fabricated.",
    }


@app.get("/api/v1/data/epc/status")
def epc_status():
    return {
        "configured": bool(core.EPC_API_URL),
        "service": "Get energy performance of buildings data",
        "source_url": "https://get-energy-performance-data.communities.gov.uk/",
        "note": "The current England and Wales service requires authorised API access. The retired legacy endpoint is not used.",
    }
