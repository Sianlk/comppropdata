from __future__ import annotations
import uuid
from fastapi.testclient import TestClient
from app.production import app
client=TestClient(app)
def account():
 email=f"ops-{uuid.uuid4().hex}@example.test";r=client.post('/api/v1/auth/register',json={'email':email,'password':'SecurePass123!','name':'Ops Test'});assert r.status_code==200,r.text;return{'Authorization':f"Bearer {r.json()['token']}"}
def test_scenario_lab_is_deterministic_and_transparent():
 r=client.post('/api/v1/calculators/scenario-lab',json={'acquisition':100000,'construction':200000,'gdv':400000,'gdv_steps_pct':[-10,0,10],'construction_steps_pct':[-10,0,10]});assert r.status_code==200,r.text;b=r.json();assert len(b['matrix'])==9;assert b['base']['profit']==100000;assert b['break_even_gdv']==300000
def test_decision_pack_is_owner_scoped_and_fingerprinted():
 a=account();b=account();p=client.post('/api/v1/projects',headers=a,json={'name':'Decision Pack Project','postcode':'RG45 7XX'});assert p.status_code==200;pid=p.json()['id'];j=client.get(f'/api/v1/projects/{pid}/decision-pack.json',headers=a);assert j.status_code==200,j.text;assert len(j.json()['snapshot_sha256'])==64;assert client.get(f'/api/v1/projects/{pid}/decision-pack.json',headers=b).status_code==404;pdf=client.get(f'/api/v1/projects/{pid}/decision-pack.pdf',headers=a);assert pdf.status_code==200;assert pdf.headers['content-type'].startswith('application/pdf');assert len(pdf.content)>500
def test_authenticated_mutations_create_body_free_audit_events():
 a=account();p=client.post('/api/v1/projects',headers=a,json={'name':'Audited Project'});assert p.status_code==200;events=client.get('/api/v1/audit/events',headers=a);assert events.status_code==200;rows=events.json()['events'];assert any(x['method']=='POST' and x['path']=='/api/v1/projects' for x in rows)
