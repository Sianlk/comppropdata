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
 meta=client.get('/api/v1/resources/book');assert meta.status_code==200,meta.text;body=meta.json();assert body['chapter_count']==16;assert body['reviewed']=='2026-08-30';assert body['publication_status']=='published-in-full';assert body['word_count']>10000;assert all(x['section_count']>=5 for x in body['chapters'])
 pdf=client.get('/api/v1/resources/property-development-augmented-book.pdf');assert pdf.status_code==200,pdf.text;assert pdf.headers['content-type'].startswith('application/pdf');assert len(pdf.content)>30000

def test_free_site_signal_is_a_deliberately_small_screening_asset():
 pdf=client.get('/api/v1/resources/site-signal.pdf');assert pdf.status_code==200,pdf.text;assert pdf.headers['content-type'].startswith('application/pdf');assert len(pdf.content)>2000

def test_planning_fee_calculator_uses_dated_2026_schedule():
 r=client.post('/api/v1/calculators/planning-fee-england',json={'category':'householder_single','dwellings':1});assert r.status_code==200,r.text;body=r.json();assert body['estimated_statutory_fee']==548;assert body['effective_schedule_date']=='2026-04-01';assert 'publishing.service.gov.uk' in body['source']['url']

def test_cil_calculator_requires_explicit_local_rate_and_does_not_invent_one():
 r=client.post('/api/v1/calculators/cil-estimate',json={'chargeable_area_sqm':100,'local_rate_per_sqm':200,'index_multiplier':1.1,'existing_lawful_floor_area_credit_sqm':10});assert r.status_code==200,r.text;body=r.json();assert body['net_chargeable_area_sqm']==90;assert body['estimated_cil_after_user_entered_relief']==19800;assert 'does not invent a local CIL rate' in body['evidence_rule']

def test_max_land_bid_and_build_cost_are_transparent_deterministic_arithmetic():
 build=client.post('/api/v1/calculators/manual-build-cost',json={'area_sqft':1000,'cost_per_sqft':200,'preliminaries_pct':10,'contingency_pct':5,'vat_pct':0});assert build.status_code==200,build.text;assert build.json()['total_build_cost']==231000
 bid=client.post('/api/v1/calculators/max-land-bid',json={'gdv':1000000,'construction':400000,'professional_fees':50000,'finance':50000,'contingency':30000,'planning_obligations':20000,'sales_and_marketing':20000,'other_costs':10000,'acquisition_costs_excluding_land':20000,'target_profit_pct_gdv':20});assert bid.status_code==200,bid.text;assert bid.json()['maximum_land_price_before_unmodelled_tax_risk_and_abnormals']==200000
