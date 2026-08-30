from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .bootstrap import app
from . import full_stack as stack
from . import agents
from .development_strategy import DossierRequest, dossier_bundle
from .market_intelligence import PROPERTYDATA_API_KEY, SiteValueRequest, site_value


class PostcodeFeasibilityRequest(BaseModel):
    postcode: str = Field(min_length=3, max_length=16)
    address: str = ''
    proposal: str = Field(default='', max_length=6000)
    local_authority_domain: str = ''
    purchase_price: float = Field(default=0, ge=0)
    pre_development_sqft: float = Field(default=1, gt=0)
    post_development_sqft: float = Field(default=1, gt=0)
    acquisition_costs: float = Field(default=0, ge=0)
    professional_fees: float = Field(default=0, ge=0)
    professional_fee_pct: float = Field(default=12, ge=0, le=50)
    finance: float = Field(default=0, ge=0)
    contingency: float = Field(default=0, ge=0)
    contingency_pct: float = Field(default=7.5, ge=0, le=50)
    other_costs: float = Field(default=0, ge=0)
    target_profit: float = Field(default=0, ge=0)
    target_profit_pct_gdv: float = Field(default=20, ge=0, le=80)
    finish_quality: Literal['basic','medium','premium'] = 'medium'
    project_type: Literal['new_build','refurb_heavy','refurb_moderate','refurb_light'] = 'new_build'
    unit_mix: dict[str,int] = Field(default_factory=dict)
    project_id: int | None = None


def _has_financial_model(r: PostcodeFeasibilityRequest) -> bool:
    return r.post_development_sqft > 10


@app.post('/api/v1/development/postcode-feasibility')
async def postcode_feasibility(r: PostcodeFeasibilityRequest, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    dossier_task = dossier_bundle(DossierRequest(
        postcode=r.postcode,
        address=r.address,
        proposal=r.proposal,
        local_authority_domain=r.local_authority_domain,
        depth='enriched' if PROPERTYDATA_API_KEY else 'official',
        include_live_policy=True,
        project_id=r.project_id,
    ))
    appraisal_task = site_value(SiteValueRequest(
        postcode=r.postcode,
        purchase_price=r.purchase_price,
        pre_development_sqft=max(r.pre_development_sqft,1),
        post_development_sqft=max(r.post_development_sqft,1),
        acquisition_costs=r.acquisition_costs,
        professional_fees=r.professional_fees,
        professional_fee_pct=r.professional_fee_pct,
        finance=r.finance,
        contingency=r.contingency,
        contingency_pct=r.contingency_pct,
        other_costs=r.other_costs,
        target_profit=r.target_profit,
        target_profit_pct_gdv=r.target_profit_pct_gdv,
        finish_quality=r.finish_quality,
        project_type=r.project_type,
        unit_mix=r.unit_mix,
    ), user) if _has_financial_model(r) else asyncio.sleep(0, result={'status':'not_modelled','reason':'Add proposed floor area to run the commercial model.'})
    dossier, appraisal = await asyncio.gather(dossier_task, appraisal_task)

    goal = '''Create a policy-aware development feasibility challenge for this postcode/address. Use the live retrieved local and national planning material, site evidence and commercial model. Do NOT invent an approval probability, policy obligation, CIL/S106 amount, affordable-housing requirement, consultant fee, build cost or GDV. Specifically identify: (1) the current planning-policy layers retrieved and their dates/status; (2) policy/constraint issues capable of changing use, massing, density, floorspace, access, parking, design or technical scope; (3) policy-triggered costs or obligations that are numerically ESTABLISHED from supplied evidence; (4) policy-triggered costs that are NOT ESTABLISHED and therefore must remain a visible appraisal allowance/gap; (5) the strongest assumptions in the residual/site-value model; (6) the next evidence that could move the residual materially; and (7) lower-risk, balanced and upside investigation directions. If no proposal was supplied, treat this as an opportunity scan and state what development directions deserve investigation rather than inventing a scheme.'''
    commercial = await agents._run('commercial', agents.AgentRunRequest(
        goal=goal,
        project_id=r.project_id,
        context={'postcode':r.postcode,'address':r.address,'proposal':r.proposal or 'not fixed','live_site_dossier':dossier,'base_appraisal':appraisal},
        web_research=False,
    ), user, s)

    site_scan: dict[str,Any] | None = None
    if not r.proposal.strip():
        site_scan = await agents._run('site-analyst', agents.AgentRunRequest(
            goal='From the postcode-led dossier only, identify plausible development questions/directions worth investigating, the strongest immediate constraints, and the minimum additional evidence required before a concept should be costed. Do not invent site capacity, units or planning probability.',
            project_id=r.project_id,
            context={'live_site_dossier':dossier},
            web_research=False,
        ), user, s)

    return {
        'mode':'postcode-first-policy-aware-feasibility',
        'postcode':r.postcode.upper(),
        'address':r.address,
        'proposal':r.proposal or None,
        'live_site_dossier':dossier,
        'base_commercial_model':appraisal,
        'policy_and_commercial_challenge':commercial,
        'postcode_opportunity_scan':site_scan,
        'calculation_rule':'Numeric appraisal outputs use explicit/provider evidence. Live policy can trigger an allowance or evidence gap, but the system never invents a CIL/S106/affordable-housing/technical cost merely to make the residual look complete.',
        'freshness_rule':'National and local planning policy is retrieved live for the analysis. Every material policy proposition must retain source/status/date or be labelled NOT ESTABLISHED.',
    }
