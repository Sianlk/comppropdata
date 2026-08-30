from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from .bootstrap import app

PLANNING_FEE_SOURCE = 'https://assets.publishing.service.gov.uk/media/69a073bb07d7bff3604d6df6/Planning_fees_-_annual_indexation_from_1_April_2026.pdf'
PLANNING_FEE_EFFECTIVE = '2026-04-01'


class ManualBuildCostRequest(BaseModel):
    area_sqft: float = Field(gt=0)
    cost_per_sqft: float = Field(gt=0)
    preliminaries_pct: float = Field(default=0, ge=0, le=100)
    contingency_pct: float = Field(default=0, ge=0, le=100)
    vat_pct: float = Field(default=0, ge=0, le=30)


class MaxLandBidRequest(BaseModel):
    gdv: float = Field(gt=0)
    construction: float = Field(default=0, ge=0)
    professional_fees: float = Field(default=0, ge=0)
    finance: float = Field(default=0, ge=0)
    contingency: float = Field(default=0, ge=0)
    planning_obligations: float = Field(default=0, ge=0)
    sales_and_marketing: float = Field(default=0, ge=0)
    other_costs: float = Field(default=0, ge=0)
    acquisition_costs_excluding_land: float = Field(default=0, ge=0)
    target_profit_pct_gdv: float = Field(default=20, ge=0, le=80)


class ProfitTargetRequest(BaseModel):
    gdv: float = Field(gt=0)
    total_cost_excluding_profit: float = Field(ge=0)
    target_profit_pct_gdv: float = Field(default=20, ge=0, le=80)
    target_profit_pct_cost: float = Field(default=0, ge=0, le=200)


class CILRequest(BaseModel):
    chargeable_area_sqm: float = Field(ge=0)
    local_rate_per_sqm: float = Field(ge=0)
    index_multiplier: float = Field(default=1, gt=0)
    relief_or_exemption_pct: float = Field(default=0, ge=0, le=100)
    existing_lawful_floor_area_credit_sqm: float = Field(default=0, ge=0)


class PlanningFeeRequest(BaseModel):
    category: Literal[
        'householder_single',
        'householder_multiple',
        'dwelling_full',
        'change_use_to_dwellings',
        'other_change_of_use',
        'other_operations_floor_area',
        'prior_approval_householder',
        'prior_approval_class_ma',
        'discharge_householder',
        'discharge_other',
        'non_material_householder',
        'non_material_other',
    ]
    dwellings: int = Field(default=1, ge=0, le=10000)
    additional_dwellings: int = Field(default=0, ge=0, le=10000)
    gross_new_floor_area_sqm: float = Field(default=0, ge=0)


def _dwelling_fee(count: int) -> float:
    if count <= 0:
        return 0
    if count < 10:
        return 610 * count
    if count <= 50:
        return 659 * count
    return min(427537, 32578 + 196 * (count - 50))


def _other_floor_area_fee(area: float) -> float:
    if area <= 40:
        return 309
    if area < 1000:
        return 610 * math.ceil(area / 75)
    if area <= 3750:
        return 659 * math.ceil(area / 75)
    return min(427537, 32578 + 196 * math.ceil((area - 3750) / 75))


@app.post('/api/v1/calculators/manual-build-cost')
def manual_build_cost(r: ManualBuildCostRequest):
    base = r.area_sqft * r.cost_per_sqft
    preliminaries = base * r.preliminaries_pct / 100
    subtotal = base + preliminaries
    contingency = subtotal * r.contingency_pct / 100
    before_vat = subtotal + contingency
    vat = before_vat * r.vat_pct / 100
    return {
        'base_build_cost': round(base, 2),
        'preliminaries': round(preliminaries, 2),
        'contingency': round(contingency, 2),
        'vat': round(vat, 2),
        'total_build_cost': round(before_vat + vat, 2),
        'effective_cost_per_sqft': round((before_vat + vat) / r.area_sqft, 2),
        'assumptions': r.model_dump(),
        'note': 'Deterministic arithmetic from user-entered area and rate. It is not a QS cost plan or tender price.',
    }


@app.post('/api/v1/calculators/max-land-bid')
def max_land_bid(r: MaxLandBidRequest):
    target_profit = r.gdv * r.target_profit_pct_gdv / 100
    non_land = (
        r.construction + r.professional_fees + r.finance + r.contingency +
        r.planning_obligations + r.sales_and_marketing + r.other_costs +
        r.acquisition_costs_excluding_land
    )
    residual = r.gdv - non_land - target_profit
    return {
        'gdv': r.gdv,
        'target_profit': round(target_profit, 2),
        'non_land_costs': round(non_land, 2),
        'maximum_land_price_before_unmodelled_tax_risk_and_abnormals': round(residual, 2),
        'margin_of_safety_rule': 'Reduce the calculated maximum bid for any unpriced tax, CIL/S106, abnormal works, title risk, programme risk or evidence gap.',
        'assumptions': r.model_dump(),
        'note': 'Residual arithmetic only; not a valuation or recommendation to acquire land.',
    }


@app.post('/api/v1/calculators/profit-target')
def profit_target(r: ProfitTargetRequest):
    actual_profit = r.gdv - r.total_cost_excluding_profit
    target_gdv = r.gdv * r.target_profit_pct_gdv / 100
    target_cost = r.total_cost_excluding_profit * r.target_profit_pct_cost / 100 if r.target_profit_pct_cost else 0
    required = max(target_gdv, target_cost)
    return {
        'actual_profit': round(actual_profit, 2),
        'actual_margin_on_gdv_pct': round(actual_profit / r.gdv * 100, 2),
        'actual_margin_on_cost_pct': round(actual_profit / r.total_cost_excluding_profit * 100, 2) if r.total_cost_excluding_profit else None,
        'target_profit_required': round(required, 2),
        'headroom_above_target': round(actual_profit - required, 2),
        'meets_target': actual_profit >= required,
        'assumptions': r.model_dump(),
        'note': 'Commercial arithmetic only. Target return is a user assumption, not an investment recommendation.',
    }


@app.post('/api/v1/calculators/cil-estimate')
def cil_estimate(r: CILRequest):
    net_area = max(0, r.chargeable_area_sqm - r.existing_lawful_floor_area_credit_sqm)
    gross = net_area * r.local_rate_per_sqm * r.index_multiplier
    relief = gross * r.relief_or_exemption_pct / 100
    return {
        'net_chargeable_area_sqm': round(net_area, 2),
        'gross_estimated_cil': round(gross, 2),
        'relief_or_exemption_allowance': round(relief, 2),
        'estimated_cil_after_user_entered_relief': round(max(0, gross - relief), 2),
        'assumptions': r.model_dump(),
        'evidence_rule': 'The local charging schedule, indexation basis, lawful existing floorspace credit and any relief/exemption must be verified for the actual site. The platform does not invent a local CIL rate.',
        'note': 'Illustrative CIL arithmetic, not a liability notice or legal/planning advice.',
    }


@app.post('/api/v1/calculators/planning-fee-england')
def planning_fee_england(r: PlanningFeeRequest):
    c = r.category
    if c == 'householder_single': fee = 548
    elif c == 'householder_multiple': fee = 1083
    elif c == 'dwelling_full': fee = _dwelling_fee(r.dwellings)
    elif c == 'change_use_to_dwellings': fee = _dwelling_fee(r.additional_dwellings or r.dwellings)
    elif c == 'other_change_of_use': fee = 610
    elif c == 'other_operations_floor_area': fee = _other_floor_area_fee(r.gross_new_floor_area_sqm)
    elif c == 'prior_approval_householder': fee = 249
    elif c == 'prior_approval_class_ma': fee = 260 * r.dwellings
    elif c == 'discharge_householder': fee = 89
    elif c == 'discharge_other': fee = 309
    elif c == 'non_material_householder': fee = 46
    elif c == 'non_material_other': fee = 309
    else: fee = 0
    return {
        'estimated_statutory_fee': round(float(fee), 2),
        'category': c,
        'effective_schedule_date': PLANNING_FEE_EFFECTIVE,
        'source': {
            'name': 'MHCLG planning fees — annual indexation from 1 April 2026',
            'url': PLANNING_FEE_SOURCE,
            'retrieved_rule': 'Fee table embedded for selected common categories; verify the current statutory schedule before submission.',
        },
        'scope_limit': 'Selected common England categories only. Portal service charges, local discretionary/pre-application fees, statutory-consultee surcharges and future local/default fee changes are not added unless explicitly entered elsewhere.',
    }
