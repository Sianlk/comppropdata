from __future__ import annotations
import uuid
from fastapi.testclient import TestClient
from app.production import app
client=TestClient(app)
def account():
 email=f"user-{uuid.uuid4().hex}@example.test";r=client.post('/api/v1/auth/register',json={'email':email,'password':'SecurePass123!','name':'Test User'});assert r.status_code==200,r.text;return r.json()['token']
def test_health_and_system_status():
 assert client.get('/health').status_code==200;assert client.get('/api/v1/system/status').status_code==200
def test_appraisal_math():
 r=client.post('/api/v1/calculators/appraisal',json={'acquisition':100000,'construction':200000,'gdv':400000});assert r.status_code==200;assert r.json()['total_development_cost']==300000;assert r.json()['profit']==100000
def test_auth_project_lifecycle():
 token=account();h={'Authorization':f'Bearer {token}'};p=client.post('/api/v1/projects',headers=h,json={'name':'Test Site','postcode':'RG45 7XX'});assert p.status_code==200;pid=p.json()['id'];assert client.get('/api/v1/projects',headers=h).status_code==200;assert client.get(f'/api/v1/projects/{pid}',headers=h).status_code==200
def test_variation_requires_approval_evidence_on_create_and_update():
 token=account();h={'Authorization':f'Bearer {token}'};p=client.post('/api/v1/projects',headers=h,json={'name':'Control Test'});pid=p.json()['id'];bad_create=client.post(f'/api/v1/projects/{pid}/registers',headers=h,json={'kind':'variation','title':'Change wall','status':'Approved','data':{'cost':1000}});assert bad_create.status_code==422;created=client.post(f'/api/v1/projects/{pid}/registers',headers=h,json={'kind':'variation','title':'Change wall','status':'Open','data':{'cost':1000}});assert created.status_code==200;rid=created.json()['id'];bad=client.patch(f'/api/v1/projects/{pid}/registers/{rid}',headers=h,json={'status':'Approved','data':{'cost':1000}});assert bad.status_code==422;good=client.patch(f'/api/v1/projects/{pid}/registers/{rid}',headers=h,json={'status':'Approved','data':{'cost':1000,'approval_evidence':'Signed instruction SI-001'}});assert good.status_code==200;assert good.json()['status']=='Approved'
def test_protected_ai_requires_auth_in_production():
 r=client.post('/api/v1/ai/analyse',json={'text':'hello'});assert r.status_code==401
def test_generated_site_triage_pdf():
 r=client.get('/api/v1/resources/site-triage.pdf');assert r.status_code==200;assert r.headers['content-type'].startswith('application/pdf');assert len(r.content)>1000
