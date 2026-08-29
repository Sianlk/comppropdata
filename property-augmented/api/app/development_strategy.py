from __future__ import annotations

import asyncio
import re
from typing import Any, Literal

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .bootstrap import app, ai_v2
from . import full_stack as stack
from . import main as core
from . import agents
from .intelligence import _web_research
from .geo_intelligence import geospatial_context, GeoContextRequest, HMLR_INSPIRE, HMLR_SIM
from .market_intelligence import enrichment_bundle, propertydata, PROPERTYDATA_API_KEY

NPPF='https://www.gov.uk/guidance/national-planning-policy-framework'
PINS='https://www.gov.uk/government/publications/planning-inspectorate-appeals-database'
APPROVED_DOCS='https://www.gov.uk/government/collections/approved-documents'
PPG='https://www.gov.uk/government/collections/planning-practice-guidance'

def _domain(value):return value.strip().lower().replace('https://','').replace('http://','').split('/',1)[0]
def _research_domains(domain:str,baseline:list[str]|None=None):
 d=_domain(domain)
 # If the user does not know the council domain, leave search unrestricted so live research can identify the official LPA site.
 return list(dict.fromkeys((baseline or [])+[d])) if d else []
def _tokens(text):
 stop={'the','and','for','with','from','into','this','that','use','of','to','a','an','in','on','at','is','are','proposed','proposal'};return {x for x in re.findall(r'[a-z0-9]+',str(text).lower()) if len(x)>2 and x not in stop}
def _walk(v):
 out=[]
 if isinstance(v,dict):
  out.append(v)
  for x in v.values():out.extend(_walk(x))
 elif isinstance(v,list):
  for x in v:out.extend(_walk(x))
 return out

def measured_planning_sample(data,proposal):
 pt=_tokens(proposal);rows=[]
 for x in _walk(data):
  desc=next((str(x.get(k)) for k in ('description','proposal','development_description','summary','title') if x.get(k)),'');decision=next((str(x.get(k)) for k in ('decision','decision_text','decision_rating','status','outcome') if x.get(k)),'')
  if not desc or not decision:continue
  dt=_tokens(desc);u=pt|dt;sim=len(pt&dt)/len(u) if u else 0
  if sim<.05:continue
  dl=decision.lower();outcome='positive' if any(z in dl for z in ('approve','grant','permit','allowed')) else 'negative' if any(z in dl for z in ('refus','dismiss')) else 'other';rows.append({'description':desc[:1000],'decision':decision[:300],'outcome':outcome,'similarity':round(sim,3)})
 rows.sort(key=lambda x:x['similarity'],reverse=True);rows=rows[:50];positive=sum(x['outcome']=='positive' for x in rows);negative=sum(x['outcome']=='negative' for x in rows);decided=positive+negative
 return {'matched_cases':rows,'sample_size':len(rows),'decided_sample_size':decided,'positive':positive,'negative':negative,'historical_positive_share_pct':round(positive/decided*100,1) if decided>=5 else None,'rule':'Historical local outcomes describe the retrieved comparable sample; they are not an approval probability. Material differences and policy changes must be analysed.'}

agents.AGENTS.update({
 'planning-prospects':{'name':'Planning Prospects & Appeals Analyst','stage':'SITE','purpose':'Compare a proposal with current policy, nearby decisions and appeal evidence without guaranteeing permission.','instruction':'Use measured local outcomes only where an actual comparable sample exists. Explain differences. Never invent or overstate approval probability. Distinguish current development plan, national policy, guidance, technical evidence, precedent and planning judgement.','keywords':['planning prospects','appeal','permission','refusal','policy','precedent']},
 'architectural-concept':{'name':'Development Concept & Architecture Analyst','stage':'SITE','purpose':'Generate evidence-led development concept options and architect briefing parameters.','instruction':'Produce concept-level options, not certified architecture. Never present dimensions, fire, structure, access, daylight, highways or compliance as validated unless the evidence supports it. Give lower-risk, balanced and higher-upside options with assumptions.','keywords':['architecture','massing','layout','units','design','site capacity']},
 'regulatory-coordinator':{'name':'Building Regulations & Technical Coordinator','stage':'BUILD','purpose':'Map Building Regulations, structure, fire, access, energy, drainage and specialist evidence required for a scheme.','instruction':'Do not certify compliance. Identify applicable workstreams, competent professionals, current source documents, interfaces and evidence gates.','keywords':['building regulations','structure','fire','transport','environment','technical']},
 'transport-environment':{'name':'Transport & Environmental Evidence Analyst','stage':'SITE','purpose':'Coordinate highways, parking, servicing, flood, drainage, ecology/BNG, trees, noise, air, contamination, heritage and daylight evidence.','instruction':'Local validation and site triggers determine scope. Do not declare impacts acceptable without competent evidence and authority/professional judgement.','keywords':['transport','highways','parking','flood','ecology','bng','noise','air','heritage']},
 'application-pack':{'name':'Planning Application Pack Coordinator','stage':'SITE','purpose':'Turn assembled evidence into a tailored submission/commissioning pack without fabricating professional reports.','instruction':'Draft only what can properly be drafted from verified evidence. Never impersonate an architect, engineer, ecologist, transport, acoustic or other professional. Mark professional evidence as TO COMMISSION / PROFESSIONAL SIGN-OFF REQUIRED.','keywords':['planning statement','validation','application pack','design access statement','consultant brief']},
})

REGULATORY_MATRIX=[
 {'code':'A','topic':'Structure','lead':'Structural engineer','source':'https://www.gov.uk/government/publications/structure-approved-document-a'},
 {'code':'B','topic':'Fire safety','lead':'Architect / fire engineer as applicable','source':'https://www.gov.uk/government/publications/fire-safety-approved-document-b'},
 {'code':'C','topic':'Site preparation, contaminants and moisture','lead':'Architect / ground/environmental specialists as applicable','source':APPROVED_DOCS},
 {'code':'E','topic':'Resistance to sound','lead':'Architect / acoustic consultant','source':APPROVED_DOCS},
 {'code':'F','topic':'Ventilation','lead':'Architect / MEP','source':'https://www.gov.uk/government/publications/approved-document-f-2026'},
 {'code':'G','topic':'Sanitation, hot water and water efficiency','lead':'Architect / MEP','source':APPROVED_DOCS},
 {'code':'H','topic':'Drainage and waste disposal','lead':'Civil/drainage engineer','source':APPROVED_DOCS},
 {'code':'K','topic':'Protection from falling, collision and impact','lead':'Architect / structural engineer','source':APPROVED_DOCS},
 {'code':'L','topic':'Conservation of fuel and power','lead':'Energy assessor / architect / MEP','source':'https://www.gov.uk/government/publications/approved-document-l-2026'},
 {'code':'M','topic':'Access to and use of buildings','lead':'Architect / access consultant','source':'https://www.gov.uk/government/publications/access-to-and-use-of-buildings-approved-document-m'},
 {'code':'O','topic':'Overheating','lead':'Energy/overheating assessor / architect','source':APPROVED_DOCS},
 {'code':'P','topic':'Electrical safety in dwellings','lead':'Competent electrical designer/installer','source':APPROVED_DOCS},
 {'code':'Q','topic':'Security in dwellings','lead':'Architect','source':APPROVED_DOCS},
 {'code':'R','topic':'Electronic communications infrastructure','lead':'Architect / telecoms','source':APPROVED_DOCS},
 {'code':'S','topic':'EV charging infrastructure','lead':'Architect / MEP','source':APPROVED_DOCS},
 {'code':'T','topic':'Toilet accommodation','lead':'Architect','source':APPROVED_DOCS},
]

class DossierRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';proposal:str='';local_authority_domain:str='';depth:Literal['official','enriched']='enriched';include_live_policy:bool=True;project_id:int|None=None
class PlanningProspectsRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';proposal:str=Field(min_length=3,max_length=5000);local_authority_domain:str='';category:str='';application_type:str='';max_age_days:int=Field(default=3650,ge=90,le=7300);project_id:int|None=None
class PolicyPackRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';proposal:str='';local_authority_domain:str=Field(default='',max_length=250);project_id:int|None=None
class ConceptRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';development_goal:str=Field(min_length=3,max_length=5000);site_area_sqm:float|None=Field(default=None,gt=0);existing_gia_sqm:float|None=Field(default=None,ge=0);budget_gbp:float|None=Field(default=None,ge=0);project_id:int|None=None
class FeePlanRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';proposal:str=Field(min_length=3,max_length=5000);local_authority_domain:str='';project_id:int|None=None
class ApplicationPackRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';proposal:str=Field(min_length=3,max_length=8000);local_authority_domain:str='';project_id:int|None=None;include_market_evidence:bool=True

async def dossier_bundle(r:DossierRequest):
 site,geo=await asyncio.gather(core.site(core.SiteRequest(postcode=r.postcode,address=r.address)),geospatial_context(GeoContextRequest(postcode=r.postcode,address=r.address,radius_m=350)));market=await enrichment_bundle(r.postcode) if r.depth=='enriched' else {'configured':False,'status':'not_requested'};policy=None
 if r.include_live_policy:
  domains=_research_domains(r.local_authority_domain,['gov.uk','planning.data.gov.uk','legislation.gov.uk','acp.planninginspectorate.gov.uk'])
  discovery='If the local authority domain was not supplied, first identify the official local planning authority and its official website, then use its primary planning documents.' if not r.local_authority_domain else 'Use the supplied local-authority domain as a primary source.'
  policy=await _web_research(f'{discovery} Build the current address-specific planning evidence pack for {r.address or r.postcode}. Proposal: {r.proposal or "not fixed"}. Retrieve the adopted development plan and relevant policies, emerging plan where material, SPDs/design guides, local validation list, parking/highways standards, CIL and planning obligations, BNG/ecology, flood/drainage, heritage, trees, noise/air, transport requirements, recent materially similar permissions/refusals and relevant appeal decisions. Give current/effective dates and mark anything not found NOT ESTABLISHED.',{'official_site_data':site},domains)
 return {'site':site,'geospatial':geo,'market_and_title_enrichment':market,'current_policy_and_precedent':policy,'building_regulations':REGULATORY_MATRIX,'land_registration':{'inspire':HMLR_INSPIRE,'official_confirmation':HMLR_SIM,'warning':'INSPIRE is an indicative registered-freehold screen; Search of the Index Map is the official route to confirm registration.'},'evidence_rule':'This dossier aggregates evidence; it does not itself establish a legal boundary, valuation, planning permission, measured survey, structural design or regulatory approval.'}

@app.post('/api/v1/site/dossier')
async def site_dossier(r:DossierRequest,user:stack.User=Depends(stack.me)):return await dossier_bundle(r)

@app.post('/api/v1/planning/policy-pack')
async def policy_pack(r:PolicyPackRequest,user:stack.User=Depends(stack.me)):
 domain=_domain(r.local_authority_domain);domains=_research_domains(domain,['gov.uk','planning.data.gov.uk','legislation.gov.uk'])
 discover='Identify the official local planning authority and official council planning domain for this address before retrieving documents.' if not domain else f'Use {domain} as the local-authority primary domain.'
 research=await _web_research(f'{discover} For {r.address or r.postcode} and proposal {r.proposal or "not fixed"}, retrieve and organise the complete current local planning policy stack: adopted local plan/development plan documents and maps, saved policies, emerging plan if material, SPDs/SAPs/design codes, local validation list, CIL charging schedule, S106/affordable housing guidance, parking/highways standards, BNG/ecology, heritage, trees, flood/drainage, noise/air and any neighbourhood plan. Identify document status, adoption/effective date, relevant policy references and missing documents. Do not rely on snippets where the primary document is available.',{},domains)
 return {'authority_domain_supplied':domain or None,'research':research,'national_baseline':{'nppf':NPPF,'ppg':PPG},'rule':'The development plan and applicable policy must be verified at the decision date.'}

@app.post('/api/v1/planning/prospects')
async def planning_prospects(r:PlanningProspectsRequest,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 site=await core.site(core.SiteRequest(postcode=r.postcode,address=r.address));pd=await propertydata('planning-applications',{'postcode':r.postcode,'category':r.category,'application_type':r.application_type,'max_age':r.max_age_days});sample=measured_planning_sample(pd.get('data') if pd.get('configured') else None,r.proposal);domains=_research_domains(r.local_authority_domain,['gov.uk','planning.data.gov.uk','acp.planninginspectorate.gov.uk'])
 discovery='Identify and use the official local planning authority site as well as primary appeal/decision sources.' if not r.local_authority_domain else 'Use the supplied local-authority domain plus primary appeal/decision sources.'
 research=await _web_research(f'{discovery} For {r.address or r.postcode}, find the strongest materially comparable planning decisions and appeal decisions relevant to: {r.proposal}. For each, identify proposal, site/context, decision, date, decisive policy/evidence issues and why it is comparable or distinguishable. Then identify what evidence or design changes appear to have resolved or failed each issue. Use primary decision notices/appeal decisions where available and current policy.',{'site':site,'measured_local_sample':sample},domains)
 req=agents.AgentRunRequest(goal='Assess the planning evidence strategy. Give: lower-risk planning-led direction, balanced direction and higher-upside direction; strongest supporting points; strongest vulnerabilities; material precedent distinctions; exact reports/drawings/evidence needed; likely refusal themes to design out. Historical outcome statistics are descriptive only, never a guaranteed permission probability.',project_id=r.project_id,context={'site':site,'proposal':r.proposal,'measured_sample':sample,'precedent_and_appeal_research':research},web_research=False);analysis=await agents._run('planning-prospects',req,user,s)
 return {'proposal':r.proposal,'measured_local_sample':sample,'precedent_and_appeal_research':research,'specialist_analysis':analysis,'warning':'This is evidence-led planning strategy, not a permission guarantee or substitute for the decision-maker.'}

@app.post('/api/v1/development/concepts')
async def concepts(r:ConceptRequest,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 dossier=await dossier_bundle(DossierRequest(postcode=r.postcode,address=r.address,proposal=r.development_goal,depth='enriched' if PROPERTYDATA_API_KEY else 'official',include_live_policy=False,project_id=r.project_id));req=agents.AgentRunRequest(goal='Produce three concept-level development strategies: lower-risk/planning-led, balanced, and higher-upside. For each set out likely use, massing/storeys, indicative unit/accommodation strategy, access/parking/servicing, architecture/context response, technical workstreams, planning dependencies, buildability/commercial questions and exact assumptions. Create a professional architect brief after the options. Do not claim a design is compliant or buildable until verified.',project_id=r.project_id,context={'dossier':dossier,'development_goal':r.development_goal,'site_area_sqm':r.site_area_sqm,'existing_gia_sqm':r.existing_gia_sqm,'budget_gbp':r.budget_gbp},web_research=False);return await agents._run('architectural-concept',req,user,s)

@app.post('/api/v1/development/fee-plan')
async def fee_plan(r:FeePlanRequest,user:stack.User=Depends(stack.me)):
 domains=_research_domains(r.local_authority_domain,['gov.uk','planningportal.co.uk']);discover='Identify the official local planning authority fee/validation pages.' if not r.local_authority_domain else 'Use the supplied local authority as a primary source.'
 research=await _web_research(f'{discover} For {r.address or r.postcode}, proposal: {r.proposal}, identify the likely planning/technical submission pack and CURRENT costs where a primary/provider-published source exists. Include statutory planning fee, local pre-application fee, local building-control fee if published, Search of Index Map if relevant, and published fee evidence for architect, measured/topographical survey, structural engineer, transport/highways, acoustic, ecology/BNG, drainage/flood, arboriculture, heritage, daylight/sunlight, air quality/contamination, energy/SAP/SBEM and other likely specialists. Never invent consultant prices: where no current published price exists say PRICE NOT ESTABLISHED and specify the quote needed.',{},domains)
 return {'research':research,'rule':'Statutory/provider-published fees can be established from a current source; bespoke consultant prices remain NOT ESTABLISHED until quoted.'}

@app.post('/api/v1/development/application-pack')
async def application_pack(r:ApplicationPackRequest,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 dossier,fees=await asyncio.gather(dossier_bundle(DossierRequest(postcode=r.postcode,address=r.address,proposal=r.proposal,local_authority_domain=r.local_authority_domain,depth='enriched' if r.include_market_evidence and PROPERTYDATA_API_KEY else 'official',include_live_policy=True,project_id=r.project_id)),fee_plan(FeePlanRequest(postcode=r.postcode,address=r.address,proposal=r.proposal,local_authority_domain=r.local_authority_domain,project_id=r.project_id),user))
 goal='''Create a production-ready PLANNING APPLICATION PREPARATION PACK from the evidence provided. It must include: 1) executive site/proposal summary; 2) evidence status and unresolved assumptions; 3) policy matrix mapping the proposal to current national/local policies; 4) planning statement first draft with source placeholders and no invented claims; 5) Design & Access Statement content/architect brief; 6) validation checklist; 7) drawing/survey schedule; 8) consultant commissioning briefs for every triggered discipline; 9) transport/highways/parking/servicing evidence brief; 10) flood/drainage brief; 11) ecology/BNG/trees brief; 12) heritage/townscape/daylight/noise/air/contamination briefs where triggered; 13) Building Regulations/structural/fire/energy coordination matrix; 14) precedent and appeal appendix plan; 15) likely objection/refusal themes and evidence to answer them; 16) current fee/cost schedule, using PRICE NOT ESTABLISHED where no sourced price exists; 17) submission sequence and dependencies; 18) exact professional sign-offs still required. Never fabricate a specialist report or imply that AI text is professional evidence.'''
 req=agents.AgentRunRequest(goal=goal,project_id=r.project_id,context={'address':r.address,'postcode':r.postcode,'proposal':r.proposal,'dossier':dossier,'fee_plan':fees,'regulations':REGULATORY_MATRIX},web_research=False);structured=await agents._run('application-pack',req,user,s)
 narrative=await ai_v2('report-writer',goal+'\nWrite the useful draft text and templates in clearly headed sections. Every unsourced material statement must be labelled [VERIFY] or [NOT ESTABLISHED].',{'dossier':dossier,'fee_plan':fees,'structured_agent_report':structured.get('report')})
 return {'address':r.address,'postcode':r.postcode,'proposal':r.proposal,'structured_pack':structured,'draft_content':narrative,'source_dossier':dossier,'fee_plan':fees,'professional_boundary':'The generated planning statement/DAS material is a draft coordination asset. Technical, legal, architectural, engineering, ecology, transport, acoustic, valuation and other professional outputs require the relevant competent author/reviewer where applicable.'}

@app.get('/api/v1/regulations/matrix')
def regulations():
 return {'building_regulations':REGULATORY_MATRIX,'planning':[{'topic':'National policy','source':NPPF},{'topic':'Planning Practice Guidance','source':PPG},{'topic':'Local development plan / SPD / validation','source':'address-specific authority policy pack required'},{'topic':'Appeals evidence','source':PINS}],'structure':{'statutory_baseline':'Approved Document A and Building Regulations; project-specific structural design/standards must be set by a competent structural engineer.','source':'https://www.gov.uk/government/publications/structure-approved-document-a'},'transport_environment':[{'topic':'Access/highways/parking/servicing','evidence':'local highway standards, transport statement/assessment, visibility/swept-path evidence as triggered'},{'topic':'Flood/drainage','evidence':'EA/local flood evidence plus site-specific FRA/drainage strategy as triggered'},{'topic':'Ecology/BNG/trees','evidence':'current DEFRA/MHCLG/local policy and competent ecological/arboricultural evidence'},{'topic':'Noise/air/contamination','evidence':'site/context and local-validation-triggered specialist evidence'},{'topic':'Heritage/townscape/daylight','evidence':'heritage/design/daylight evidence proportionate to context and impacts'}],'note':'Coordination matrix, not a building-control, engineering or planning compliance certificate.'}
