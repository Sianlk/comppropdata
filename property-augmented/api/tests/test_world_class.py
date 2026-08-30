from __future__ import annotations
import asyncio
from fastapi.testclient import TestClient
from app.production import app
from app import geo_intelligence as geo

client=TestClient(app)

def test_source_catalogue_exposes_licensed_mapping_and_no_rightmove_scraping():
 r=client.get('/api/v1/intelligence/source-catalogue');assert r.status_code==200,r.text
 rows={x['id']:x for x in r.json()['sources']}
 assert {'os-maps','os-features','os-places','google-maps','ea-lidar','hmlr-inspire','hmlr-sim','rightmove-public','rightmove-authorised'}.issubset(rows)
 assert rows['rightmove-public']['access']=='no-automated-scraping'

def test_registration_workflow_does_not_mislabel_unregistered_land():
 r=client.get('/api/v1/land/registration-guide');assert r.status_code==200,r.text
 body=r.json();assert 'does not prove unregistered land' in body['inspire']['limitation'].lower();assert 'confirms whether searched land is registered' in body['official_sim']['what_it_does'].lower()

def test_planning_adapter_uses_current_brownfield_dataset(monkeypatch):
 captured={}
 async def fake(url,params=None,**kwargs):captured['params']=params;return {'entities':[]}
 monkeypatch.setattr(geo.core,'getjson',fake)
 body=asyncio.run(geo.corrected_planning(51.5,-0.1));datasets=[v for k,v in captured['params'] if k=='dataset']
 assert 'brownfield-land' in datasets;assert 'brownfield-site' not in datasets;assert body['data']=={'entities':[]}

def test_world_class_paid_intelligence_requires_authentication():
 assert client.post('/api/v1/site/dossier',json={'postcode':'SW1A 1AA'}).status_code==401
 assert client.post('/api/v1/planning/prospects',json={'postcode':'SW1A 1AA','proposal':'rear extension'}).status_code==401
 assert client.post('/api/v1/planning/policy-pack',json={'postcode':'SW1A 1AA'}).status_code==401
 assert client.post('/api/v1/development/application-pack',json={'postcode':'SW1A 1AA','proposal':'rear extension'}).status_code==401
 assert client.post('/api/v1/market/deal-scan',json={'postcode':'SW1A 1AA'}).status_code==401
 assert client.post('/api/v1/development/site-value',json={'postcode':'SW1A 1AA','purchase_price':1,'pre_development_sqft':1,'post_development_sqft':2}).status_code==401
 assert client.post('/api/v1/development/postcode-feasibility',json={'postcode':'SW1A 1AA'}).status_code==401

def test_regulatory_matrix_covers_structure_fire_energy_and_environment():
 r=client.get('/api/v1/regulations/matrix');assert r.status_code==200,r.text;body=r.json();codes={x['code'] for x in body['building_regulations']};assert {'A','B','L','M','O'}.issubset(codes);assert len(body['transport_environment'])>=4

def test_os_tiles_fail_closed_without_private_key():
 r=client.get('/api/v1/maps/os/10/511/340.png');assert r.status_code==503

def test_complete_book_is_published_and_generated_from_same_source():
 meta=client.get('/api/v1/resources/book');assert meta.status_code==200,meta.text;body=meta.json();assert body['chapter_count']==16;assert body['reviewed']=='2026-08-30'
 pdf=client.get('/api/v1/resources/property-development-augmented-book.pdf');assert pdf.status_code==200,pdf.text;assert pdf.headers['content-type'].startswith('application/pdf');assert len(pdf.content)>10000

def test_free_site_signal_is_a_deliberately_small_screening_asset():
 pdf=client.get('/api/v1/resources/site-signal.pdf');assert pdf.status_code==200,pdf.text;assert pdf.headers['content-type'].startswith('application/pdf');assert len(pdf.content)>2000
