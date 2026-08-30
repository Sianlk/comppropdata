from __future__ import annotations
import uuid
from fastapi.testclient import TestClient
from app.production import app
client=TestClient(app)
def account():
 email=f"dd-{uuid.uuid4().hex}@example.test";r=client.post('/api/v1/auth/register',json={'email':email,'password':'SecurePass123!','name':'DD Test'});assert r.status_code==200;return{'Authorization':f"Bearer {r.json()['token']}"}
def project(h):
 r=client.post('/api/v1/projects',headers=h,json={'name':'Due Diligence Site'});assert r.status_code==200;return r.json()['id']
def test_template_initialisation_and_verified_requires_evidence():
 h=account();pid=project(h);t=client.get('/api/v1/due-diligence/template');assert t.status_code==200;assert len(t.json()['items'])>=20;init=client.post(f'/api/v1/projects/{pid}/due-diligence/initialise',headers=h);assert init.status_code==200;matrix=client.get(f'/api/v1/projects/{pid}/due-diligence',headers=h);assert matrix.status_code==200;items=matrix.json()['items'];assert len(items)==len(t.json()['items']);item=items[0];bad=client.patch(f"/api/v1/projects/{pid}/due-diligence/{item['id']}",headers=h,json={'status':'Verified','evidence_refs':[]});assert bad.status_code==422;good=client.patch(f"/api/v1/projects/{pid}/due-diligence/{item['id']}",headers=h,json={'status':'Verified','evidence_refs':['Land Registry title AB123456 reviewed 2026-08-30']});assert good.status_code==200;assert good.json()['status']=='Verified';updated=client.get(f'/api/v1/projects/{pid}/due-diligence',headers=h).json();assert updated['counts']['Verified']==1
