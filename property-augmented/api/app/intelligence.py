from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import main as core
from .bootstrap import CORE_POLICY, OPENAI_MODEL, _output_text, app


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


POLICY_LIBRARY: list[dict[str, Any]] = [
    {"id":"nppf-2026","category":"planning-policy","title":"National Planning Policy Framework","jurisdiction":"England","url":"https://www.gov.uk/guidance/national-planning-policy-framework","publisher":"Ministry of Housing, Communities and Local Government","status":"current-source","effective_context":"New NPPF published 17 August 2026; verify the live page and linked document before relying on paragraph numbering or wording.","authoritative":True},
    {"id":"planning-practice-guidance","category":"planning-guidance","title":"Planning Practice Guidance","jurisdiction":"England","url":"https://www.gov.uk/government/collections/planning-practice-guidance","publisher":"Ministry of Housing, Communities and Local Government","status":"live-guidance","effective_context":"Topic guidance is updated independently; retrieve the current topic page for a live project.","authoritative":True},
    {"id":"planning-data","category":"planning-data","title":"Planning Data","jurisdiction":"England","url":"https://www.planning.data.gov.uk/docs","publisher":"Ministry of Housing, Communities and Local Government","status":"beta","effective_context":"Government Planning Data is beta. Dataset and local-authority coverage/completeness vary.","authoritative":True},
    {"id":"approved-documents","category":"building-regulations","title":"Approved Documents collection","jurisdiction":"England","url":"https://www.gov.uk/government/collections/approved-documents","publisher":"Ministry of Housing, Communities and Local Government","status":"statutory-guidance-collection","effective_context":"Check the individual Approved Document and transitional provisions that apply to the specific work and date.","authoritative":True},
    {"id":"approved-document-l-2026","category":"building-regulations","title":"Approved Document L (2026)","jurisdiction":"England","url":"https://www.gov.uk/government/publications/approved-document-l-2026","publisher":"Ministry of Housing, Communities and Local Government","status":"statutory-guidance","effective_context":"Published 24 March 2026. Earlier standards can continue to apply to work within transitional arrangements.","authoritative":True},
    {"id":"approved-document-f-2026","category":"building-regulations","title":"Approved Document F (2026)","jurisdiction":"England","url":"https://www.gov.uk/government/publications/approved-document-f-2026","publisher":"Ministry of Housing, Communities and Local Government","status":"statutory-guidance","effective_context":"Published 24 March 2026. Verify which edition applies to the project.","authoritative":True},
    {"id":"building-regulations-approval","category":"building-control","title":"Building regulations approval","jurisdiction":"England","url":"https://www.gov.uk/building-regulations-approval","publisher":"GOV.UK","status":"live-guidance","effective_context":"General building-control route; higher-risk buildings follow the BSR regime. A Building Safety Levy is due to apply to certain residential applications/initial notices from 1 October 2026.","authoritative":True},
    {"id":"higher-risk-building-control","category":"building-safety","title":"Building control approval for higher-risk buildings","jurisdiction":"England","url":"https://www.gov.uk/guidance/building-control-approval-for-higher-risk-buildings","publisher":"Building Safety Regulator","status":"live-guidance","effective_context":"Use for current BSR building-control requirements for higher-risk buildings; verify project classification and current process.","authoritative":True},
    {"id":"higher-risk-design-construction","category":"building-safety","title":"Design and construction of higher-risk buildings","jurisdiction":"England","url":"https://www.gov.uk/government/collections/design-and-construction-of-higher-risk-buildings","publisher":"Building Safety Regulator","status":"guidance-collection","effective_context":"Includes building-control approval, change control, completion, competence and golden-thread guidance.","authoritative":True},
    {"id":"bng-guidance","category":"biodiversity","title":"Biodiversity net gain","jurisdiction":"England","url":"https://www.gov.uk/guidance/biodiversity-net-gain","publisher":"Ministry of Housing, Communities and Local Government","status":"planning-practice-guidance","effective_context":"Updated 31 July 2026. BNG rules and exemptions changed during 2026; verify applicability and application date.","authoritative":True},
    {"id":"bng-developer-collection","category":"biodiversity","title":"Biodiversity net gain guidance for developers, land managers and authorities","jurisdiction":"England","url":"https://www.gov.uk/government/collections/biodiversity-net-gain-guidance-for-developers-land-managers-and-authorities","publisher":"Department for Environment, Food & Rural Affairs","status":"live-guidance-collection","effective_context":"Collection updated 27 August 2026; contains current developer guidance, metrics, exemptions and registers.","authoritative":True},
    {"id":"bng-plan","category":"biodiversity","title":"Biodiversity gain plan","jurisdiction":"England","url":"https://www.gov.uk/government/publications/biodiversity-gain-plan","publisher":"Department for Environment, Food & Rural Affairs","status":"current-form-and-guidance","effective_context":"Template updated 6 August 2026. Verify the version relevant to the permission/application date.","authoritative":True},
    {"id":"land-registry-ppd","category":"property-data","title":"HM Land Registry Price Paid Data","jurisdiction":"England and Wales","url":"https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads","publisher":"HM Land Registry","status":"official-data","effective_context":"Sold-price evidence is not a valuation. Registration lag, exclusions and data corrections can apply.","authoritative":True},
    {"id":"ea-flood-monitoring","category":"environment","title":"Environment Agency Flood Monitoring API","jurisdiction":"England","url":"https://environment.data.gov.uk/flood-monitoring/doc/reference","publisher":"Environment Agency","status":"live-data","effective_context":"Operational flood-monitoring information is not a substitute for flood-risk assessment, planning maps or safety-critical advice.","authoritative":True},
    {"id":"epc-data","category":"energy","title":"Get energy performance of buildings data","jurisdiction":"England and Wales","url":"https://get-energy-performance-data.communities.gov.uk/","publisher":"Ministry of Housing, Communities and Local Government","status":"official-data-service","effective_context":"Authorised API/account access is required. Do not use the retired legacy endpoint as a live dependency.","authoritative":True},
    {"id":"companies-house","category":"company-data","title":"Companies House API","jurisdiction":"United Kingdom","url":"https://developer.company-information.service.gov.uk/","publisher":"Companies House","status":"official-data-service","effective_context":"Use company number and official filing data for verification; search results alone do not establish financial standing or beneficial ownership conclusions.","authoritative":True},
    {"id":"local-plans-2026","category":"local-plan","title":"Local plans: examination process under the 2026 regulations","jurisdiction":"England","url":"https://www.gov.uk/guidance/local-plans-the-examination-process-new-style-local-plan-2026-regulations","publisher":"Planning Inspectorate","status":"current-guidance","effective_context":"During 2026 both legacy and new-style local-plan systems can operate. The live local authority development plan remains project-specific.","authoritative":True},
    {"id":"s106-affordable-housing-2026","category":"planning-obligations","title":"Section 106 affordable housing engagement guidance","jurisdiction":"England","url":"https://www.gov.uk/government/publications/section-106-affordable-housing-engagement-guidance","publisher":"Ministry of Housing, Communities and Local Government","status":"current-guidance","effective_context":"Published 25 August 2026. This does not replace the development plan, viability evidence, legal agreement or local authority requirements.","authoritative":True},
]


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    local_authority_domain: str = ""
    web_research: bool = True


class WebDeepResearch(BaseModel):
    topic: str = Field(min_length=3, max_length=5000)
    postcode: str = ""
    address: str = ""
    allowed_domains: list[str] = Field(default_factory=list)
    official_first: bool = True


def _normalise_domain(value: str) -> str:
    value = value.strip().lower().replace("https://", "").replace("http://", "").split("/", 1)[0]
    return value


def _extract_sources(data: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for source in action.get("sources", []) or []:
                if not isinstance(source, dict):
                    continue
                url = source.get("url") or source.get("link")
                if url and url not in seen:
                    seen.add(url)
                    out.append({"url": url, "title": source.get("title"), "type": source.get("type"), "source": "OpenAI web_search"})
        if item.get("type") == "message":
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                for ann in content.get("annotations", []) or []:
                    if not isinstance(ann, dict):
                        continue
                    citation = ann.get("url_citation") if isinstance(ann.get("url_citation"), dict) else ann
                    url = citation.get("url") if isinstance(citation, dict) else None
                    if url and url not in seen:
                        seen.add(url)
                        out.append({"url": url, "title": citation.get("title"), "type": "citation", "source": "OpenAI web_search"})
    return out


async def _web_research(prompt: str, context: Any = None, domains: list[str] | None = None) -> dict[str, Any]:
    if not core.OPENAI_API_KEY:
        return {"configured": False, "content": "Web research AI is not configured; set OPENAI_API_KEY.", "sources": []}
    clean_domains = list(dict.fromkeys(_normalise_domain(x) for x in (domains or []) if _normalise_domain(x)))[:100]
    tool: dict[str, Any] = {"type": "web_search", "search_context_size": "high"}
    if clean_domains:
        tool["filters"] = {"allowed_domains": clean_domains}
    payload = {
        "model": OPENAI_MODEL,
        "reasoning": {"effort": "high"},
        "tools": [tool],
        "tool_choice": "required",
        "include": ["web_search_call.action.sources"],
        "instructions": CORE_POLICY + "\nFor this research task, search the live web. Prefer primary, official and first-party sources; resolve material contradictions; include current dates; distinguish national policy from local policy; and do not treat an SEO page, forum, aggregator or AI-generated page as authority when a primary source exists.",
        "input": f"PROJECT / PROVIDED CONTEXT\n{json.dumps(context or {}, default=str, ensure_ascii=False)[:120000]}\n\nRESEARCH TASK\n{prompt}",
    }
    async with httpx.AsyncClient(timeout=150) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {core.OPENAI_API_KEY}", "Content-Type": "application/json"}, json=payload)
    if response.status_code >= 400:
        raise HTTPException(502, f"Web research provider error {response.status_code}: {response.text[:500]}")
    data = response.json()
    return {"configured": True, "content": _output_text(data), "sources": _extract_sources(data), "model": data.get("model", OPENAI_MODEL), "usage": data.get("usage"), "response_id": data.get("id"), "researched_at": now()}


@app.get("/api/v1/policy/library")
def policy_library(category: str = ""):
    rows = POLICY_LIBRARY
    if category:
        rows = [x for x in rows if x["category"] == category]
    return {"items": rows, "count": len(rows), "retrieved_at": now(), "note": "National/official source index. Local plan, SPD, CIL, validation-list and local policy requirements remain authority- and site-specific and must be retrieved from the relevant local authority."}


@app.post("/api/v1/policy/search")
async def policy_search(r: PolicySearchRequest):
    q = r.query.strip()
    local_matches = [x for x in POLICY_LIBRARY if q.lower() in (x["title"] + " " + x["category"] + " " + x["effective_context"]).lower()]
    gov = await core.govuk(q)
    research = None
    if r.web_research:
        domains = ["gov.uk", "planning.data.gov.uk", "legislation.gov.uk"]
        if r.local_authority_domain:
            domains.append(r.local_authority_domain)
        research = await _web_research(
            f"Research the current official policy/guidance position relevant to: {q}. Prioritise current effective documents, identify update/effective dates, distinguish national from local policy, and say NOT ESTABLISHED where the available material does not resolve the point.",
            {"curated_matches": local_matches, "govuk_discovery": gov},
            domains,
        )
    return {"query": q, "curated_matches": local_matches, "govuk_discovery": gov, "web_research": research, "retrieved_at": now(), "local_policy_warning": "A national search cannot establish the full development plan or local validation/CIL/SPD position for a site. Verify the relevant local authority sources."}


@app.post("/api/v1/research/web-deep")
async def web_deep_research(r: WebDeepResearch):
    bundle: dict[str, Any] = {"topic": r.topic, "govuk_discovery": await core.govuk(r.topic)}
    if r.postcode:
        bundle["site_intelligence"] = await core.site(core.SiteRequest(postcode=r.postcode, address=r.address))
    domains = r.allowed_domains
    instruction = f"Deeply research this UK property/development/construction topic: {r.topic}. Follow material second-order leads, resolve conflicts where possible, include dates and measurable facts, and provide a decision-useful brief with established facts, interpretation, uncertainty, missing evidence and verification actions."
    if r.official_first:
        instruction += " Prefer government, regulator, local-authority, legislation, official data and primary professional/industry sources over aggregators."
    web = await _web_research(instruction, bundle, domains)
    return {"status": "completed", "analysis": web, "source_bundle": bundle, "completed_at": now(), "caveat": "Live web research is decision support. Verify current policy wording, local authority documents, professional opinions and material project facts in the underlying sources."}
