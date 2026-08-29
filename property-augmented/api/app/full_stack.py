from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from .main import app

DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./property_augmented.db')
JWT_SECRET=os.getenv('JWT_SECRET','dev-change-me')
JWT_HOURS=int(os.getenv('JWT_EXPIRE_HOURS','24'))
FRONTEND_URL=os.getenv('FRONTEND_URL','http://localhost:3000')
ASSETS=Path(os.getenv('PRODUCT_ASSET_DIR','/assets'))
STRIPE_SECRET_KEY=os.getenv('STRIPE_SECRET_KEY','')
STRIPE_WEBHOOK_SECRET=os.getenv('STRIPE_WEBHOOK_SECRET','')
STRIPE_PRICE_OS=os.getenv('STRIPE_PRICE_OS','')
STRIPE_PRICE_CONSULT=os.getenv('STRIPE_PRICE_CONSULT','')

class Base(DeclarativeBase): pass
class User(Base):
 __tablename__='pda_users'; id:Mapped[int]=mapped_column(Integer,primary_key=True); email:Mapped[str]=mapped_column(String(320),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); name:Mapped[str]=mapped_column(String(255),default=''); is_admin:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Project(Base):
 __tablename__='pda_projects'; id:Mapped[int]=mapped_column(Integer,primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('pda_users.id'),index=True); name:Mapped[str]=mapped_column(String(255)); address:Mapped[str]=mapped_column(String(500),default=''); postcode:Mapped[str]=mapped_column(String(20),default=''); strategy:Mapped[str]=mapped_column(Text,default=''); metadata_json:Mapped[str]=mapped_column(Text,default='{}'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc)); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Register(Base):
 __tablename__='pda_registers'; id:Mapped[int]=mapped_column(Integer,primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('pda_users.id'),index=True); project_id:Mapped[int]=mapped_column(ForeignKey('pda_projects.id'),index=True); kind:Mapped[str]=mapped_column(String(40),index=True); title:Mapped[str]=mapped_column(String(500),default=''); status:Mapped[str]=mapped_column(String(100),default='Open'); data_json:Mapped[str]=mapped_column(Text,default='{}'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc)); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Lead(Base):
 __tablename__='pda_leads'; id:Mapped[int]=mapped_column(Integer,primary_key=True); email:Mapped[str]=mapped_column(String(320),index=True); name:Mapped[str]=mapped_column(String(255),default=''); source:Mapped[str]=mapped_column(String(100),default='website'); consent:Mapped[bool]=mapped_column(Boolean,default=False); payload_json:Mapped[str]=mapped_column(Text,default='{}'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Purchase(Base):
 __tablename__='pda_purchases'; id:Mapped[int]=mapped_column(Integer,primary_key=True); user_id:Mapped[int|None]=mapped_column(ForeignKey('pda_users.id'),nullable=True,index=True); email:Mapped[str]=mapped_column(String(320),default=''); product_slug:Mapped[str]=mapped_column(String(120),index=True); provider_ref:Mapped[str]=mapped_column(String(255),unique=True); amount:Mapped[float]=mapped_column(Float,default=0); currency:Mapped[str]=mapped_column(String(10),default='gbp'); status:Mapped[str]=mapped_column(String(50),default='paid'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {}
engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args=connect_args)
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
Base.metadata.create_all(engine)
def db():
 s=SessionLocal()
 try: yield s
 finally: s.close()
def b64(b:bytes)->str: return base64.urlsafe_b64encode(b).decode().rstrip('=')
def unb64(s:str)->bytes: return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def phash(password:str)->str:
 salt=secrets.token_bytes(16); derived=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32); return f'scrypt${b64(salt)}${b64(derived)}'
def pverify(password:str,stored:str)->bool:
 try:
  scheme,salt_b64,hash_b64=stored.split('$',2)
  if scheme!='scrypt': return False
  derived=hashlib.scrypt(password.encode(),salt=unb64(salt_b64),n=2**14,r=8,p=1,dklen=32)
  return hmac.compare_digest(b64(derived),hash_b64)
 except Exception: return False
def token(payload:dict[str,Any])->str:
 header=b64(b'{"alg":"HS256","typ":"JWT"}'); body=b64(json.dumps(payload,separators=(',',':')).encode()); sig=b64(hmac.new(JWT_SECRET.encode(),f'{header}.{body}'.encode(),hashlib.sha256).digest()); return f'{header}.{body}.{sig}'
def decode(value:str)->dict[str,Any]:
 try:
  header,body,sig=value.split('.',2)
  expected=b64(hmac.new(JWT_SECRET.encode(),f'{header}.{body}'.encode(),hashlib.sha256).digest())
  if not hmac.compare_digest(sig,expected): raise ValueError('bad signature')
  payload=json.loads(unb64(body))
  if float(payload.get('exp',0)) < datetime.now(timezone.utc).timestamp(): raise ValueError('expired')
  return payload
 except Exception as exc: raise HTTPException(401,'Invalid or expired token') from exc
def me(authorization:str|None=Header(default=None),s:Session=Depends(db)):
 if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Authentication required')
 payload=decode(authorization.split(' ',1)[1]); user=s.get(User,int(payload['sub']))
 if not user: raise HTTPException(401,'User not found')
 return user

class Auth(BaseModel): email:str; password:str=Field(min_length=8,max_length=128); name:str=''
class ProjectIn(BaseModel): name:str; address:str=''; postcode:str=''; strategy:str=''; metadata:dict[str,Any]=Field(default_factory=dict)
class RegisterIn(BaseModel): kind:str; title:str=''; status:str='Open'; data:dict[str,Any]=Field(default_factory=dict)
class LeadIn(BaseModel): email:str; name:str=''; source:str='website'; consent:bool=False; payload:dict[str,Any]=Field(default_factory=dict)

@app.post('/api/v1/auth/register')
def register(r:Auth,s:Session=Depends(db)):
 email=r.email.strip().lower()
 if s.query(User).filter(User.email==email).first(): raise HTTPException(409,'Email already registered')
 user=User(email=email,password_hash=phash(r.password),name=r.name); s.add(user); s.commit(); s.refresh(user)
 exp=(datetime.now(timezone.utc)+timedelta(hours=JWT_HOURS)).timestamp()
 return {'token':token({'sub':str(user.id),'email':user.email,'exp':exp}),'user':{'id':user.id,'email':user.email,'name':user.name}}
@app.post('/api/v1/auth/login')
def login(r:Auth,s:Session=Depends(db)):
 user=s.query(User).filter(User.email==r.email.strip().lower()).first()
 if not user or not pverify(r.password,user.password_hash): raise HTTPException(401,'Invalid email or password')
 exp=(datetime.now(timezone.utc)+timedelta(hours=JWT_HOURS)).timestamp()
 return {'token':token({'sub':str(user.id),'email':user.email,'exp':exp}),'user':{'id':user.id,'email':user.email,'name':user.name}}
@app.get('/api/v1/auth/me')
def auth_me(user:User=Depends(me)): return {'id':user.id,'email':user.email,'name':user.name,'is_admin':user.is_admin}
@app.get('/api/v1/projects')
def projects(user:User=Depends(me),s:Session=Depends(db)):
 rows=s.query(Project).filter(Project.user_id==user.id).order_by(Project.updated_at.desc()).all()
 return [{'id':p.id,'name':p.name,'address':p.address,'postcode':p.postcode,'strategy':p.strategy,'metadata':json.loads(p.metadata_json or '{}'),'updated_at':p.updated_at} for p in rows]
@app.post('/api/v1/projects')
def project_create(r:ProjectIn,user:User=Depends(me),s:Session=Depends(db)):
 p=Project(user_id=user.id,name=r.name,address=r.address,postcode=r.postcode.upper(),strategy=r.strategy,metadata_json=json.dumps(r.metadata)); s.add(p); s.commit(); s.refresh(p); return {'id':p.id,'name':p.name}
@app.get('/api/v1/projects/{project_id}')
def project_get(project_id:int,user:User=Depends(me),s:Session=Depends(db)):
 p=s.get(Project,project_id)
 if not p or p.user_id!=user.id: raise HTTPException(404,'Project not found')
 regs=s.query(Register).filter(Register.project_id==project_id,Register.user_id==user.id).all()
 return {'id':p.id,'name':p.name,'address':p.address,'postcode':p.postcode,'strategy':p.strategy,'registers':[{'id':x.id,'kind':x.kind,'title':x.title,'status':x.status,'data':json.loads(x.data_json or '{}')} for x in regs]}
@app.get('/api/v1/projects/{project_id}/registers/{kind}')
def register_list(project_id:int,kind:str,user:User=Depends(me),s:Session=Depends(db)):
 return [{'id':x.id,'kind':x.kind,'title':x.title,'status':x.status,'data':json.loads(x.data_json or '{}'),'updated_at':x.updated_at} for x in s.query(Register).filter(Register.project_id==project_id,Register.user_id==user.id,Register.kind==kind).all()]
@app.post('/api/v1/projects/{project_id}/registers')
def register_add(project_id:int,r:RegisterIn,user:User=Depends(me),s:Session=Depends(db)):
 p=s.get(Project,project_id)
 if not p or p.user_id!=user.id: raise HTTPException(404,'Project not found')
 x=Register(user_id=user.id,project_id=project_id,kind=r.kind,title=r.title,status=r.status,data_json=json.dumps(r.data)); s.add(x); s.commit(); s.refresh(x); return {'id':x.id,'status':x.status}
@app.post('/api/v1/leads')
def lead(r:LeadIn,s:Session=Depends(db)):
 if not r.consent: raise HTTPException(422,'Consent required for marketing email capture')
 x=Lead(email=r.email.strip().lower(),name=r.name,source=r.source,consent=True,payload_json=json.dumps(r.payload)); s.add(x); s.commit(); s.refresh(x); return {'id':x.id,'status':'captured'}
@app.post('/api/v1/consultancy/intake')
def intake(r:LeadIn,s:Session=Depends(db)):
 x=Lead(email=r.email.strip().lower(),name=r.name,source='consultancy-intake',consent=r.consent,payload_json=json.dumps(r.payload)); s.add(x); s.commit(); s.refresh(x); return {'id':x.id,'status':'received'}

PRODUCTS={'site-triage':{'name':'30-Minute AI Site Triage','price':0,'file':'30-minute-ai-site-triage.pdf','public':True},'ai-property-developer-os':{'name':'AI Property Developer OS','price':79,'file':'ai-property-developer-os.xlsx','public':False}}
@app.get('/api/v1/products')
def product_list(): return [{'slug':k,'name':v['name'],'price':v['price'],'public':v['public']} for k,v in PRODUCTS.items()]
@app.post('/api/v1/payments/checkout')
def checkout(payload:dict):
 if not STRIPE_SECRET_KEY: raise HTTPException(503,'Stripe not configured')
 import stripe; stripe.api_key=STRIPE_SECRET_KEY; slug=payload.get('product_slug'); price=STRIPE_PRICE_OS if slug=='ai-property-developer-os' else STRIPE_PRICE_CONSULT if slug=='development-intelligence-session' else ''
 if not price: raise HTTPException(422,'No Stripe price configured')
 session=stripe.checkout.Session.create(mode='payment',line_items=[{'price':price,'quantity':1}],success_url=f'{FRONTEND_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}',cancel_url=f'{FRONTEND_URL}/pricing',customer_email=payload.get('email'),metadata={'product_slug':slug})
 return {'url':session.url,'id':session.id}
@app.post('/api/v1/payments/webhook')
async def stripe_webhook(request:Request,s:Session=Depends(db)):
 if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET: raise HTTPException(503,'Stripe webhook not configured')
 import stripe; stripe.api_key=STRIPE_SECRET_KEY; body=await request.body(); sig=request.headers.get('stripe-signature','')
 try: event=stripe.Webhook.construct_event(body,sig,STRIPE_WEBHOOK_SECRET)
 except Exception as exc: raise HTTPException(400,'Invalid webhook') from exc
 if event['type']=='checkout.session.completed':
  obj=event['data']['object']; email=(obj.get('customer_details') or {}).get('email',''); slug=(obj.get('metadata') or {}).get('product_slug','')
  if slug and not s.query(Purchase).filter(Purchase.provider_ref==obj['id']).first():
   user=s.query(User).filter(User.email==email.lower()).first() if email else None
   s.add(Purchase(user_id=user.id if user else None,email=email,product_slug=slug,provider_ref=obj['id'],amount=float(obj.get('amount_total') or 0)/100,currency=obj.get('currency') or 'gbp',status='paid')); s.commit()
 return {'received':True}
@app.get('/api/v1/products/{slug}/download')
def download(slug:str,user:User=Depends(me),s:Session=Depends(db)):
 p=PRODUCTS.get(slug)
 if not p: raise HTTPException(404,'Product not found')
 if not p['public'] and not s.query(Purchase).filter(Purchase.user_id==user.id,Purchase.product_slug==slug,Purchase.status=='paid').first(): raise HTTPException(403,'No entitlement')
 path=ASSETS/p['file']
 if not path.exists(): raise HTTPException(404,'Product asset not provisioned on this deployment')
 return FileResponse(path,filename=path.name)
