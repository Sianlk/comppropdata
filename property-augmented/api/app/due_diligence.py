from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .bootstrap import app
from . import full_stack as stack


def now(): return datetime.now(timezone.utc)

TEMPLATE=[
{"code":"LEG-01","category":"Legal / title","item":"Registered title, title plan and ownership/vendor authority","materiality":"critical"},
{"code":"LEG-02","category":"Legal / title","item":"Rights of access, easements, covenants, restrictions and ransom/third-party interests","materiality":"critical"},
{"code":"LEG-03","category":"Legal / title","item":"Boundary/site extent evidence and any discrepancy requiring survey/legal review","materiality":"high"},
{"code":"PLN-01","category":"Planning","item":"Planning history, existing/lawful use and relevant previous refusals/conditions/obligations","materiality":"high"},
{"code":"PLN-02","category":"Planning","item":"Current development plan, NPPF/guidance and site-specific policy designations/constraints","materiality":"critical"},
{"code":"PLN-03","category":"Planning","item":"Local validation requirements, CIL, Section 106 and other authority-specific requirements","materiality":"high"},
{"code":"PLN-04","category":"Planning","item":"Relevant precedent/appeal evidence and material differences from the subject proposal","materiality":"medium"},
{"code":"TRN-01","category":"Access / transport","item":"Legal and physical access, highway status, visibility and servicing constraints","materiality":"critical"},
{"code":"TRN-02","category":"Access / transport","item":"Parking, cycle, refuse, turning/swept-path and sustainable transport evidence","materiality":"high"},
{"code":"ENV-01","category":"Flood / drainage","item":"Flood-zone/surface-water evidence and need for site-specific flood assessment","materiality":"critical"},
{"code":"ENV-02","category":"Flood / drainage","item":"Foul/surface-water drainage strategy, capacity and discharge/consent constraints","materiality":"high"},
{"code":"ENV-03","category":"Ecology / BNG / trees","item":"Ecology, protected species, biodiversity net gain and habitat/tree constraints","materiality":"high"},
{"code":"ENV-04","category":"Ground / contamination","item":"Ground conditions, contamination, mining/radon/geotechnical risks as applicable","materiality":"high"},
{"code":"ENV-05","category":"Heritage / townscape","item":"Listed building, conservation area, archaeology and heritage/townscape setting constraints","materiality":"high"},
{"code":"UTL-01","category":"Utilities","item":"Electricity, water, gas, telecoms and sewer availability/capacity/diversion constraints","materiality":"high"},
{"code":"TEC-01","category":"Technical / design","item":"Measured survey, levels/topography and reliable existing/proposed drawings","materiality":"critical"},
{"code":"TEC-02","category":"Technical / design","item":"Structural feasibility and any specialist engineering investigations","materiality":"high"},
{"code":"TEC-03","category":"Technical / design","item":"Noise/acoustic, air quality, daylight/sunlight, overheating or other environmental assessments as applicable","materiality":"high"},
{"code":"TEC-04","category":"Building regulations / fire","item":"Building Regulations strategy, fire/life-safety responsibilities and Building Safety Act/BSR implications as applicable","materiality":"critical"},
{"code":"COM-01","category":"Commercial","item":"GDV/value evidence with comparable rationale and valuation assumptions","materiality":"critical"},
{"code":"COM-02","category":"Commercial","item":"Construction cost evidence, exclusions, abnormal costs, professional/statutory fees and contingency","materiality":"critical"},
{"code":"COM-03","category":"Commercial","item":"Development programme/holding assumptions and sensitivity to delay/cost/GDV movement","materiality":"high"},
{"code":"FIN-01","category":"Finance / tax","item":"Finance terms, fees, covenants, drawdown/interest assumptions and funding conditions","materiality":"high"},
{"code":"FIN-02","category":"Finance / tax","item":"Tax/VAT/SDLT and ownership-structure advice where material","materiality":"high"},
{"code":"DEL-01","category":"Delivery","item":"Consultant scopes, dependencies, deliverables and appointment responsibilities","materiality":"medium"},
{"code":"DEL-02","category":"Delivery","item":"Procurement strategy, contractor scope/qualifications and programme controls","materiality":"high"},
]

STATUSES={"Not started","Researching","Evidence received","Verified","Issue identified","Not applicable"}
class DDIn(BaseModel):
 code:str=Field(min_length=2,max_length=40);category:str=Field(min_length=2,max_length=120);item:str=Field(min_length=3,max_length=1000);status:str="Not started";owner:str="";materiality:Literal["critical","high","medium","low"]="medium";evidence_refs:list[str]=Field(default_factory=list,max_length=50);evidence_date:str="";expiry_or_review_date:str="";notes:str=""
class DDPatch(BaseModel):
 status:str|None=None;owner:str|None=None;evidence_refs:list[str]|None=None;evidence_date:str|None=None;expiry_or_review_date:str|None=None;notes:str|None=None;materiality:Literal["critical","high","medium","low"]|None=None

def project(project_id:int,user:stack.User,s:Session):
 p=s.get(stack.Project,project_id)
 if not p or p.user_id!=user.id:raise HTTPException(404,"Project not found")
 return p

def serial(x:stack.Register)->dict[str,Any]:
 d=json.loads(x.data_json or "{}");return{"id":x.id,"code":d.get("code",""),"category":d.get("category",""),"item":x.title,"status":x.status,"owner":d.get("owner",""),"materiality":d.get("materiality","medium"),"evidence_refs":d.get("evidence_refs",[]),"evidence_date":d.get("evidence_date",""),"expiry_or_review_date":d.get("expiry_or_review_date",""),"notes":d.get("notes",""),"updated_at":x.updated_at}
def validate(status:str,evidence_refs:list[str]):
 if status not in STATUSES:raise HTTPException(422,"Invalid due diligence status")
 clean=[str(x).strip() for x in evidence_refs if str(x).strip()]
 if status=="Verified" and not clean:raise HTTPException(422,"Due diligence cannot be marked Verified without at least one evidence reference")
 return clean

@app.get('/api/v1/due-diligence/template')
def template():return{"items":TEMPLATE,"principle":"Verified means evidence referenced and human checked; it does not mean the project, title, planning case or investment is risk-free."}
@app.get('/api/v1/projects/{project_id}/due-diligence')
def list_dd(project_id:int,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 project(project_id,user,s);rows=s.query(stack.Register).filter(stack.Register.project_id==project_id,stack.Register.user_id==user.id,stack.Register.kind=='due_diligence').order_by(stack.Register.id).all();items=[serial(x)for x in rows];counts={status:sum(i['status']==status for i in items)for status in STATUSES};critical_open=sum(i['materiality']=='critical' and i['status'] not in {'Verified','Not applicable'} for i in items);return{"items":items,"counts":counts,"critical_open":critical_open,"evidence_coverage_pct":round((counts.get('Verified',0)+counts.get('Not applicable',0))/len(items)*100,1)if items else 0,"note":"Evidence coverage is a checklist/review measure, not a probability of success or investment score."}
@app.post('/api/v1/projects/{project_id}/due-diligence/initialise')
def initialise(project_id:int,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 p=project(project_id,user,s);existing=s.query(stack.Register).filter(stack.Register.project_id==project_id,stack.Register.user_id==user.id,stack.Register.kind=='due_diligence').all();codes={json.loads(x.data_json or '{}').get('code')for x in existing};created=0
 for t in TEMPLATE:
  if t['code'] in codes:continue
  data={**t,"owner":"","evidence_refs":[],"evidence_date":"","expiry_or_review_date":"","notes":""};s.add(stack.Register(user_id=user.id,project_id=project_id,kind='due_diligence',title=t['item'],status='Not started',data_json=json.dumps(data)));created+=1
 if created:p.updated_at=now();s.add(p)
 s.commit();return{"created":created,"total_template_items":len(TEMPLATE)}
@app.post('/api/v1/projects/{project_id}/due-diligence')
def add_dd(project_id:int,r:DDIn,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 p=project(project_id,user,s);refs=validate(r.status,r.evidence_refs);data=r.model_dump();data['evidence_refs']=refs;x=stack.Register(user_id=user.id,project_id=project_id,kind='due_diligence',title=r.item,status=r.status,data_json=json.dumps(data));s.add(x);p.updated_at=now();s.add(p);s.commit();s.refresh(x);return serial(x)
@app.patch('/api/v1/projects/{project_id}/due-diligence/{item_id}')
def patch_dd(project_id:int,item_id:int,r:DDPatch,user:stack.User=Depends(stack.me),s:Session=Depends(stack.db)):
 project(project_id,user,s);x=s.get(stack.Register,item_id)
 if not x or x.user_id!=user.id or x.project_id!=project_id or x.kind!='due_diligence':raise HTTPException(404,"Due diligence item not found")
 data=json.loads(x.data_json or '{}');status=r.status if r.status is not None else x.status;refs=r.evidence_refs if r.evidence_refs is not None else data.get('evidence_refs',[]);data['evidence_refs']=validate(status,refs)
 for key in ['owner','evidence_date','expiry_or_review_date','notes','materiality']:
  v=getattr(r,key)
  if v is not None:data[key]=v
 x.status=status;x.data_json=json.dumps(data);x.updated_at=now();s.add(x);s.commit();s.refresh(x);return serial(x)
