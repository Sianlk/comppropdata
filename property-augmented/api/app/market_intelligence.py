from __future__ import annotations

import asyncio
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .bootstrap import app
from . import full_stack as stack
from . import main as core
from . import agents

PROPERTYDATA_API_KEY=os.getenv('PROPERTYDATA_API_KEY','')
PROPERTYDATA_DOCS='https://propertydata.co.uk/api/documentation'
RIGHTMOVE_TERMS='https://www.rightmove.co.uk/c/terms-of-use/'
RIGHTMOVE_API_TERMS='https://api-docs.rightmove.co.uk/terms'

def now():return datetime.now(timezone.utc).isoformat()

ALLOWED_ENDPOINTS={'address-match-uprn','uprn','uprn-title','uprns','prices','prices-per-sqf','sold-prices','sold-prices-per-sqf','planning-applications','build-cost','rebuild-cost','development-calculator','development-gdv','buildings','floor-areas','freeholds','title','title-use-class','land-registry-documents','energy-efficiency','flood-risk','green-belt','conservation-area','listed-buildings','ptal','sourced-properties','sourced-property','property-types','demand','growth','growth-psf','yields','valuation-sale','valuation-historical','tenure-types','site-plan-documents'}

async def propertydata(endpoint:str,params:dict[str,Any]):
 if not PROPERTYDATA_API_KEY:return {'configured':False,'status':'provider_not_configured','endpoint':endpoint,'data':None}
 if endpoint not in ALLOWED_ENDPOINTS:raise HTTPException(422,'Unsupported licensed property-data endpoint')
 u=f'https://api.propertydata.co.uk/{endpoint}';clean={k:v for k,v in params.items() if v not in (None,'',[],{})}
 try:
  async with httpx.AsyncClient(timeout=65,follow_redirects=True) as c:r=await c.get(u,params=clean,headers={'X-API-Key':PROPERTYDATA_API_KEY});r.raise_for_status();d=r.json()
  return {'configured':True,'status':'ok','endpoint':endpoint,'data':d,'source':{'name':'PropertyData API','url':f'{PROPERTYDATA_DOCS}/{endpoint}','retrieved_at':now(),'caveat':'Licensed commercial enrichment. Preserve provider rights; asking prices/modelled values are not achieved-sale evidence or a Red Book valuation.'}}
 except Exception as e:return {'configured':True,'status':'error','endpoint':endpoint,'error':str(e),'data':None}

async def enrichment_bundle(postcode:str):
 if not PROPERTYDATA_API_KEY:return {'configured':False,'status':'provider_not_configured','note':'Set PROPERTYDATA_API_KEY for licensed live-market, planning, build-cost and title enrichment.'}
 requests=[('prices',{'postcode':postcode}),('prices-per-sqf',{'postcode':postcode}),('sold-prices',{'postcode':postcode}),('sold-prices-per-sqf',{'postcode':postcode}),('planning-applications',{'postcode':postcode,'max_age':3650}),('freeholds',{'postcode':postcode}),('energy-efficiency',{'postcode':postcode}),('floor-areas',{'postcode':postcode}),('property-types',{'postcode':postcode}),('flood-risk',{'postcode':postcode}),('green-belt',{'postcode':postcode}),('conservation-area',{'postcode':postcode}),('listed-buildings',{'postcode':postcode})]
 rows=await asyncio.gather(*(propertydata(ep,p) for ep,p in requests));return {'configured':True,'providers':{x['endpoint']:x for x in rows},'credit_note':'Provider calls consume credits. Cache/reuse only as allowed by the commercial licence.'}

def walk_dicts(v):
 out=[]
 if isinstance(v,dict):
  out.append(v)
  for x in v.values():out.extend(walk_dicts(x))
 elif isinstance(v,list):
  for x in v:out.extend(walk_dicts(x))
 return out

def as_number(v):
 if v is None or isinstance(v,bool):return None
 if isinstance(v,(int,float)):return float(v)
 try:return float(re.sub(r'[^0-9.-]','',str(v)))
 except Exception:return None

def metric(data,names:list[str]):
 wanted={re.sub(r'[^a-z0-9]','',x.lower()) for x in names}
 for row in walk_dicts(data):
  for key,value in row.items():
   norm=re.sub(r'[^a-z0-9]','',str(key).lower())
   if norm in wanted:
    n=as_number(value)
    if n is not None:return n
 return None

class MarketScanRequest(BaseModel):
 postcode:str=Field(min_length=2,max_length=16);lists:list[str]=Field(default_factory=lambda:['unmodernised-properties','reduced-properties','slow-to-sell-properties']);max_price:float|None=Field(default=None,gt=0);strategy:str=Field(default='development opportunity',max_length=1200);radius_miles:int=Field(default=20,ge=1,le=200);results:int=Field(default=20,ge=10,le=100);page:int=Field(default=1,ge=1,le=25)
class SiteValueRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);purchase_price:float=Field(default=0,ge=0);pre_development_sqft:float=Field(gt=0);post_development_sqft:float=Field(gt=0);acquisition_costs:float=Field(default=0,ge=0);professional_fees:float=Field(default=0,ge=0);professional_fee_pct:float=Field(default=12,ge=0,le=50);finance:float=Field(default=0,ge=0);contingency:float=Field(default=0,ge=0);contingency_pct:float=Field(default=7.5,ge=0,le=50);other_costs:float=Field(default=0,ge=0);target_profit:float=Field(default=0,ge=0);target_profit_pct_gdv:float=Field(default=20,ge=0,le=80);finish_quality:Literal['basic','medium','premium']='medium';project_type:Literal['new_build','refurb_heavy','refurb_moderate','refurb_light']='new_build';unit_mix:dict[str,int]=Field(default_factory=dict)

agents.AGENTS.update({'deal-scout':{'name':'Development Deal Scout','stage':'SITE','purpose':'Prioritise licensed market opportunities for further investigation using price, planning and development evidence.','instruction':'Never scrape prohibited portals, recommend purchase, call a listing undervalued from asking-price evidence alone, or infer permission. Rank investigation priority and evidence gaps only.','keywords':['deal','listing','below market','development opportunity','sourcing']},'land-title':{'name':'Land & Title Evidence Analyst','stage':'SITE','purpose':'Challenge title, registered-land, boundary, UPRN and ownership evidence before development reliance.','instruction':'INSPIRE absence does not prove unregistered land. Distinguish title plan, index polygon, address/UPRN and OS mapping. Require official/legal evidence for title conclusions.','keywords':['title','freehold','unregistered','boundary','uprn','land registry']}})

@app.get('/api/v1/data/propertydata/{endpoint}')
async def propertydata_proxy(endpoint:str,postcode:str='',location:str='',town:str='',max_age:int|None=None,points:int|None=None):return await propertydata(endpoint,{'postcode':postcode,'location':location,'town':town,'max_age':max_age,'points':points})

@app.post('/api/v1/market/deal-scan')
async def deal_scan(r:MarketScanRequest,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 if not PROPERTYDATA_API_KEY:
  return {'configured':False,'status':'licensed_market_feed_required','message':"The platform deliberately does not scrape Rightmove's public site because its terms prohibit scraping, bots and crawlers. Configure a licensed market feed instead.",'approved_routes':[{'name':'PropertyData API','url':PROPERTYDATA_DOCS,'note':'Licensed normalized market/sourcing data.'},{'name':'Rightmove authorised API/data feed','url':RIGHTMOVE_API_TERMS,'note':'Integrate only under an authorised agreement.'}],'rightmove_public_terms':RIGHTMOVE_TERMS}
 source=await propertydata('sourced-properties',{'postcode':r.postcode,'list':','.join(x.strip() for x in r.lists if x.strip()),'radius':r.radius_miles,'results':r.results,'page':r.page});items=[]
 for x in walk_dicts(source.get('data')):
  if not any(k in x for k in ('price','asking_price','address','precise_address','postcode','id','property_id')):continue
  price=as_number(x.get('price') or x.get('asking_price'))
  if r.max_price is not None and price is not None and price>r.max_price:continue
  address=str(x.get('precise_address') or x.get('address') or '').strip();postcode=str(x.get('postcode') or r.postcode).strip()
  if not address and price is None:continue
  items.append({'id':x.get('id') or x.get('property_id'),'address':address,'postcode':postcode,'asking_price':price,'property_type':x.get('type_standardised') or x.get('type') or x.get('property_type'),'bedrooms':x.get('bedrooms'),'source_url':x.get('url') or x.get('source_url'),'lists':x.get('lists') or x.get('list'),'reduced_by':x.get('reduced_by'),'months_on_market':x.get('months_on_market'),'plot_size_acres':x.get('plot_size_acres')})
 dedup={str(x.get('id') or (x['address'],x['asking_price'])):x for x in items};items=list(dedup.values())[:min(r.results,50)];sem=asyncio.Semaphore(5)
 async def enrich(x):
  async with sem:
   lr=await core.hmlr(x['postcode']) if x.get('postcode') else {'transactions':[]};prices=[]
   for t in lr.get('transactions',[]) or []:
    n=as_number(t.get('price'))
    if n:prices.append(n)
   median=statistics.median(prices) if prices else None;ask=x.get('asking_price');delta=round((ask/median-1)*100,1) if ask and median else None
   return {**x,'hmlr_local_transaction_count':len(prices),'hmlr_local_median_sold_price':median,'ask_vs_hmlr_median_pct':delta,'triage_signal':'investigate' if delta is not None and delta<=-10 else 'normal_review','signal_note':'Area/postcode price triage only; condition, area, tenure, title, planning, abnormal costs and true comparability are not established.'}
 enriched=await asyncio.gather(*(enrich(x) for x in items[:20]));req=agents.AgentRunRequest(goal=f'Prioritise these listings for development investigation under the strategy: {r.strategy}. Explain planning, title, value, condition and build-cost evidence needed before any conclusion. Do not recommend purchase.',context={'candidates':enriched},web_research=False);analysis=await agents._run('deal-scout',req,user,s) if enriched else None
 return {'configured':True,'candidate_count':len(enriched),'candidates':enriched,'specialist_analysis':analysis,'provider':source.get('source'),'rights_note':'Licensed market feed only; public portal scraping is disabled by design.'}

@app.post('/api/v1/development/site-value')
async def site_value(r:SiteValueRequest,user:stack.User=Depends(stack.me)):
 build_params={'postcode':r.postcode,'internal_area':r.post_development_sqft,'finish_quality':r.finish_quality,'project_type':r.project_type}
 build_task=propertydata('build-cost',build_params) if r.post_development_sqft>=600 else asyncio.sleep(0,result={'configured':bool(PROPERTYDATA_API_KEY),'status':'not_requested','reason':'build-cost provider requires internal_area >= 600 sqft'})
 calc_type='refurbish' if r.project_type.startswith('refurb') else 'demolition'
 calc_params={'postcode':r.postcode,'purchase_price':r.purchase_price,'sqft_pre_development':r.pre_development_sqft,'sqft_post_development':r.post_development_sqft,'project_type':calc_type,'finish_quality':r.finish_quality,'return_formatted_strings':'false'}
 calc_task=propertydata('development-calculator',calc_params)
 gdv_params={'postcode':r.postcode,'internal_area':r.post_development_sqft,'finish_quality':r.finish_quality,**{k:int(v) for k,v in r.unit_mix.items() if int(v)>0}}
 gdv_task=propertydata('development-gdv',gdv_params) if r.unit_mix and r.post_development_sqft>=1000 else asyncio.sleep(0,result={'configured':bool(PROPERTYDATA_API_KEY),'status':'not_requested','reason':'development-gdv requires a residential unit mix and internal_area >= 1,000 sqft'})
 build,market,sold,calc,gdv=await asyncio.gather(build_task,propertydata('prices-per-sqf',{'postcode':r.postcode}),propertydata('sold-prices-per-sqf',{'postcode':r.postcode}),calc_task,gdv_task)
 build_cost=metric(build.get('data'),['total_build_cost','build_cost','total_cost','estimated_build_cost'])
 provider_total_value=metric(calc.get('data'),['total_value','gdv','gross_development_value','post_development_value','end_value'])
 provider_profit=metric(calc.get('data'),['profit','total_profit','development_profit'])
 gdv_value=metric(gdv.get('data'),['gdv','gross_development_value','total_value','estimated_value']) or provider_total_value
 asking_psf=metric(market.get('data'),['average','average_price_per_sqft','price_per_sqft','average_psf','mean'])
 sold_psf=metric(sold.get('data'),['average','average_price_per_sqft','price_per_sqft','average_psf','mean'])
 if gdv_value is None and sold_psf is not None:gdv_value=sold_psf*r.post_development_sqft
 elif gdv_value is None and asking_psf is not None:gdv_value=asking_psf*r.post_development_sqft
 professional=r.professional_fees if r.professional_fees>0 else (build_cost*r.professional_fee_pct/100 if build_cost is not None else None)
 contingency=r.contingency if r.contingency>0 else (build_cost*r.contingency_pct/100 if build_cost is not None else None)
 target_profit=r.target_profit if r.target_profit>0 else (gdv_value*r.target_profit_pct_gdv/100 if gdv_value is not None else None)
 known=[build_cost,professional,contingency,target_profit]
 residual=None
 if gdv_value is not None and all(x is not None for x in known):residual=gdv_value-build_cost-professional-r.finance-contingency-r.other_costs-r.acquisition_costs-target_profit
 return {'purchase_price':r.purchase_price,'provider_inputs':{'build_cost_project_type':r.project_type,'development_calculator_project_type':calc_type,'finish_quality':r.finish_quality,'unit_mix':r.unit_mix},'build_cost_evidence':build,'asking_market_psf':market,'sold_market_psf':sold,'provider_development_model':calc,'provider_gdv_model':gdv,'derived_metrics':{'build_cost':build_cost,'asking_psf':asking_psf,'sold_psf':sold_psf,'evidence_backed_gdv':gdv_value,'professional_fees_used':professional,'contingency_used':contingency,'finance_used':r.finance,'other_costs_used':r.other_costs,'acquisition_costs_used':r.acquisition_costs,'target_profit_used':target_profit,'residual_site_value_before_unmodelled_tax_abnormals_and_risk':residual,'purchase_price_vs_residual':r.purchase_price-residual if residual is not None else None,'provider_profit':provider_profit},'assumptions':{'professional_fees':f'Fixed £{r.professional_fees:,.0f}' if r.professional_fees>0 else f'{r.professional_fee_pct}% of evidenced build cost','contingency':f'Fixed £{r.contingency:,.0f}' if r.contingency>0 else f'{r.contingency_pct}% of evidenced build cost','target_profit':f'Fixed £{r.target_profit:,.0f}' if r.target_profit>0 else f'{r.target_profit_pct_gdv}% of evidence-backed GDV'},'rule':'Residual site value = evidence-backed GDV minus build cost, professional fees, finance, contingency, other/acquisition costs and target profit. It remains a development appraisal, not a Red Book valuation. Taxes, CIL/S106, abnormal/site-specific costs, sales costs and finance structure must be added where material.','provider_configured':bool(PROPERTYDATA_API_KEY)}

@app.get('/api/v1/market/provider-status')
def provider_status():return {'propertydata':bool(PROPERTYDATA_API_KEY),'rightmove_public_scraping':False,'rightmove_authorised_feed_supported':True,'principle':'Use licensed market data; never evade a portal restriction.'}
