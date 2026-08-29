from __future__ import annotations

import asyncio
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote_plus

import httpx
from fastapi import HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .bootstrap import app
from . import main as core

OS_DATA_HUB_API_KEY=os.getenv('OS_DATA_HUB_API_KEY','')
GOOGLE_MAPS_BROWSER_KEY=os.getenv('GOOGLE_MAPS_BROWSER_KEY','')
GOOGLE_MAPS_SERVER_KEY=os.getenv('GOOGLE_MAPS_SERVER_KEY',GOOGLE_MAPS_BROWSER_KEY)
EA_LIDAR_DTM_WMS='https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wms'
EA_LIDAR_DSM_WMS='https://environment.data.gov.uk/spatialdata/lidar-composite-digital-surface-model-dsm-1m/wms'
HMLR_INSPIRE='https://use-land-property-data.service.gov.uk/datasets/inspire'
HMLR_INSPIRE_DOWNLOAD='https://use-land-property-data.service.gov.uk/datasets/inspire/download'
HMLR_SIM='https://www.gov.uk/get-information-about-property-and-land/search-the-index-map'
RIGHTMOVE_TERMS='https://www.rightmove.co.uk/c/terms-of-use/'
RIGHTMOVE_API_TERMS='https://api-docs.rightmove.co.uk/terms'

def now():return datetime.now(timezone.utc).isoformat()

SOURCE_CATALOGUE=[
 {'id':'os-maps','name':'Ordnance Survey Maps API','kind':'mapping','access':'licensed-api','env':'OS_DATA_HUB_API_KEY','url':'https://docs.os.uk/os-apis/accessing-os-apis/os-maps-api','use':'Detailed OS raster basemap with Road, Outdoor and Light Web Mercator layers.'},
 {'id':'os-features','name':'OS Features API / MasterMap Topography','kind':'geospatial','access':'licensed-api','env':'OS_DATA_HUB_API_KEY','url':'https://docs.os.uk/os-apis/accessing-os-apis/os-features-api','use':'Detailed building, topographic-area, line and point geometry.'},
 {'id':'os-places','name':'OS Places API','kind':'address-uprn','access':'licensed-api','env':'OS_DATA_HUB_API_KEY','url':'https://docs.os.uk/os-apis/accessing-os-apis/os-places-api','use':'Address matching, UPRN and British National Grid coordinates.'},
 {'id':'google-maps','name':'Google Maps Platform','kind':'satellite-streetview','access':'licensed-api','env':'GOOGLE_MAPS_BROWSER_KEY','url':'https://developers.google.com/maps/documentation/embed/get-started','use':'Satellite/road map and Street View display under Google Maps terms.'},
 {'id':'ea-lidar','name':'Environment Agency LiDAR 1m DTM/DSM','kind':'topography','access':'open-ogc','env':'','url':'https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m','use':'Terrain and surface context. It does not replace a current measured topographical survey where levels are material.'},
 {'id':'hmlr-inspire','name':'HM Land Registry INSPIRE Index Polygons','kind':'registered-freehold-screen','access':'open-download','env':'','url':HMLR_INSPIRE,'use':'Indicative registered freehold positions/extents; absence is not proof of unregistered land.'},
 {'id':'hmlr-sim','name':'HM Land Registry Search of the Index Map','kind':'registration-confirmation','access':'official-search','env':'','url':HMLR_SIM,'use':'Official route to confirm whether searched land is registered and return affecting title numbers.'},
 {'id':'rightmove-public','name':'Rightmove public platform','kind':'market-listings','access':'no-automated-scraping','env':'','url':RIGHTMOVE_TERMS,'use':'Not scraped. Use an authorised Rightmove feed or a licensed market-data provider.'},
 {'id':'rightmove-authorised','name':'Rightmove authorised API/data feed','kind':'market-listings','access':'licensed-only','env':'','url':RIGHTMOVE_API_TERMS,'use':'Can be integrated only under an authorised data-feed/API agreement.'},
]

def source_catalogue_rows():
 return [{**x,'configured':True if not x['env'] else bool(os.getenv(x['env'],'').strip())} for x in SOURCE_CATALOGUE]

async def _json(url,params=None,headers=None,timeout=40):
 async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as c:
  r=await c.get(url,params=params,headers=headers);r.raise_for_status();return r.json()
async def _bytes(url,params=None,timeout=60):
 async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as c:
  r=await c.get(url,params=params);r.raise_for_status();return r

async def enhanced_geocode(postcode):
 u=f"https://api.postcodes.io/postcodes/{quote_plus(core.pc(postcode))}";d=await core.getjson(u);r=d.get('result')
 if not r:raise HTTPException(422,'Postcode could not be geocoded')
 return {'postcode':r.get('postcode'),'latitude':r.get('latitude'),'longitude':r.get('longitude'),'eastings':r.get('eastings'),'northings':r.get('northings'),'admin_district':r.get('admin_district'),'admin_ward':r.get('admin_ward'),'parliamentary_constituency':r.get('parliamentary_constituency'),'region':r.get('region'),'country':r.get('country'),'source':core.src('postcodes.io',u,'Postcode centroid, not a surveyed boundary or precise address point.')}

async def corrected_planning(lat,lon):
 u='https://www.planning.data.gov.uk/entity.json';datasets=['planning-application','conservation-area','listed-building','green-belt','flood-risk-zone','article-4-direction-area','tree-preservation-zone','brownfield-land','ancient-woodland'];params=[('latitude',lat),('longitude',lon),('limit',250)]+[('dataset',x) for x in datasets]
 try:return {'data':await core.getjson(u,params=params),'queried_datasets':datasets,'source':core.src('Planning Data API',u,'Government Planning Data is beta and coverage varies by dataset/authority. No returned entity does not prove a constraint is absent.')}
 except Exception as e:return {'data':None,'error':str(e),'queried_datasets':datasets,'source':core.src('Planning Data API',u,'Unavailable/incomplete: constraint status is NOT ESTABLISHED.')}

core.geocode=enhanced_geocode
core.planning=corrected_planning
_original_hmlr=core.hmlr
async def hmlr_with_rights(postcode):
 d=await _original_hmlr(postcode)
 if d.get('source'):d['source']['caveat']='Registration lag, exclusions and corrections apply; Price Paid Data is not a valuation. Preserve HM Land Registry/OGL attribution and any applicable third-party address-data conditions.'
 return d
core.hmlr=hmlr_with_rights

class GeoContextRequest(BaseModel):
 postcode:str=Field(min_length=3,max_length=16);address:str='';radius_m:int=Field(default=300,ge=25,le=2000)

async def os_address_match(address,postcode):
 if not OS_DATA_HUB_API_KEY:return {'configured':False,'status':'provider_not_configured','matches':[]}
 q=' '.join(x for x in [address.strip(),core.pc(postcode)] if x);u='https://api.os.uk/search/places/v1/find'
 try:
  d=await _json(u,{'query':q,'maxresults':10,'output_srs':'EPSG:27700','key':OS_DATA_HUB_API_KEY});rows=[]
  for item in d.get('results',[]) or []:
   a=item.get('DPA') or item.get('LPI') or {};rows.append({'uprn':a.get('UPRN'),'address':a.get('ADDRESS'),'postcode':a.get('POSTCODE'),'easting':a.get('X_COORDINATE'),'northing':a.get('Y_COORDINATE'),'classification':a.get('CLASSIFICATION_CODE'),'logical_status':a.get('LOGICAL_STATUS_CODE')})
  return {'configured':True,'matches':rows,'source':{'name':'OS Places API','url':u,'retrieved_at':now(),'caveat':'Human-select the matching UPRN/address for the actual development land.'}}
 except Exception as e:return {'configured':True,'matches':[],'error':str(e),'source':{'name':'OS Places API','url':u,'retrieved_at':now()}}

async def os_features(e,n,radius):
 if not OS_DATA_HUB_API_KEY:return {'configured':False,'status':'provider_not_configured','features':[]}
 if e is None or n is None:return {'configured':True,'status':'no_coordinate','features':[]}
 r=min(max(radius,25),500);bbox=f'{float(e)-r},{float(n)-r},{float(e)+r},{float(n)+r},EPSG:27700';u='https://api.os.uk/features/v1/wfs'
 try:
  d=await _json(u,{'service':'WFS','request':'GetFeature','version':'2.0.0','typeNames':'Topography_TopographicArea','srsName':'EPSG:27700','bbox':bbox,'outputFormat':'GEOJSON','count':150,'key':OS_DATA_HUB_API_KEY},timeout=50)
  return {'configured':True,'features':d.get('features',[]),'source':{'name':'OS Features API / MasterMap Topography','url':u,'retrieved_at':now(),'caveat':'Mapping geometry is not a title boundary, measured survey or legal extent.'}}
 except Exception as e:return {'configured':True,'features':[],'error':str(e),'source':{'name':'OS Features API','url':u,'retrieved_at':now()}}

async def google_context(lat,lon):
 if not GOOGLE_MAPS_BROWSER_KEY:return {'configured':False,'status':'provider_not_configured'}
 meta=None
 if GOOGLE_MAPS_SERVER_KEY:
  try:meta=await _json('https://maps.googleapis.com/maps/api/streetview/metadata',{'location':f'{lat},{lon}','key':GOOGLE_MAPS_SERVER_KEY})
  except Exception as e:meta={'status':'ERROR','error':str(e)}
 key=quote_plus(GOOGLE_MAPS_BROWSER_KEY);loc=f'{lat},{lon}'
 return {'configured':True,'map_embed_url':f'https://www.google.com/maps/embed/v1/view?key={key}&center={loc}&zoom=19&maptype=satellite','streetview_embed_url':f'https://www.google.com/maps/embed/v1/streetview?key={key}&location={loc}','streetview_metadata':meta,'policy_note':'Google imagery is displayed with Google attribution and is not bulk-downloaded or cached.'}

async def geospatial_context(r:GeoContextRequest):
 g=await enhanced_geocode(r.postcode);osm,features,google=await asyncio.gather(os_address_match(r.address,r.postcode),os_features(g.get('eastings'),g.get('northings'),r.radius_m),google_context(float(g['latitude']),float(g['longitude'])))
 e,n=g.get('eastings'),g.get('northings');topo={'available':e is not None and n is not None,'dtm_image':f'/api/v1/maps/topography.png?easting={e}&northing={n}&radius_m={min(r.radius_m,1000)}&surface=dtm' if e is not None and n is not None else None,'dsm_image':f'/api/v1/maps/topography.png?easting={e}&northing={n}&radius_m={min(r.radius_m,1000)}&surface=dsm' if e is not None and n is not None else None,'source':{'name':'Environment Agency 1m LiDAR composite','caveat':'Terrain/surface context only; use a measured topographical survey where levels affect design or planning.'}}
 return {'query':r.model_dump(),'geocode':g,'os_address':osm,'os_topography_features':features,'maps':{'os_tile_template':'/api/v1/maps/os/{z}/{x}/{y}.png?layer=Light_3857' if OS_DATA_HUB_API_KEY else None,'google':google,'topography':topo},'land_registration':registration_guide(),'generated_at':now()}

_WMS={}
async def _wms_layer(base):
 if base in _WMS:return _WMS[base]
 r=await _bytes(base,{'service':'WMS','request':'GetCapabilities','version':'1.3.0'});root=ET.fromstring(r.content);names=[]
 for layer in root.iter():
  if layer.tag.endswith('Layer'):
   for child in list(layer):
    if child.tag.endswith('Name') and child.text and child.text.strip():names.append(child.text.strip())
 if not names:raise HTTPException(502,'LiDAR WMS did not expose a layer')
 _WMS[base]=names[-1];return names[-1]

@app.get('/api/v1/intelligence/source-catalogue')
def source_catalogue():return {'sources':source_catalogue_rows(),'principles':['Prefer official/open evidence for policy and statutory facts.','Use licensed commercial feeds for live listings. Public property portals are not scraped.','No aggregated result becomes a verified project fact without human review.'],'generated_at':now()}

@app.post('/api/v1/geospatial/site-context')
async def geospatial(r:GeoContextRequest):return await geospatial_context(r)

@app.get('/api/v1/maps/os/{z}/{x}/{y}.png')
async def os_map_tile(z:int,x:int,y:int,layer:str=Query(default='Light_3857')):
 if not OS_DATA_HUB_API_KEY:raise HTTPException(503,'OS Data Hub API is not configured')
 if layer not in {'Road_3857','Outdoor_3857','Light_3857'} or not 0<=z<=20 or x<0 or y<0:raise HTTPException(422,'Invalid OS tile request')
 r=await _bytes(f'https://api.os.uk/maps/raster/v1/zxy/{layer}/{z}/{x}/{y}.png',{'key':OS_DATA_HUB_API_KEY},40);return Response(content=r.content,media_type='image/png',headers={'Cache-Control':'private, max-age=300','X-Data-Source':'Ordnance Survey Maps API'})

@app.get('/api/v1/maps/topography.png')
async def topography(easting:float,northing:float,radius_m:int=Query(default=250,ge=25,le=2000),surface:Literal['dtm','dsm']='dtm'):
 base=EA_LIDAR_DTM_WMS if surface=='dtm' else EA_LIDAR_DSM_WMS;layer=await _wms_layer(base);r=float(radius_m);response=await _bytes(base,{'service':'WMS','request':'GetMap','version':'1.3.0','layers':layer,'styles':'','crs':'EPSG:27700','bbox':f'{easting-r},{northing-r},{easting+r},{northing+r}','width':768,'height':768,'format':'image/png','transparent':'false'})
 return Response(content=response.content,media_type=response.headers.get('content-type','image/png'),headers={'Cache-Control':'private, max-age=3600','X-Data-Source':f'Environment Agency LiDAR {surface.upper()}'})

@app.get('/api/v1/land/registration-guide')
def registration_guide():
 return {'inspire':{'url':HMLR_INSPIRE,'download':HMLR_INSPIRE_DOWNLOAD,'what_it_can_do':'Screen indicative registered freehold polygons and INSPIRE IDs.','limitation':'No INSPIRE polygon does not prove unregistered land; leasehold and other registrations may not be represented.'},'official_sim':{'url':HMLR_SIM,'what_it_does':'Official Search of the Index Map confirms whether searched land is registered and returns affecting title numbers/types.','fee_note':'Current GOV.UK guidance states £8 for an area covering up to 5 registered titles and £6 for each group of 10 additional titles; verify the live fee before ordering.'},'workflow':['Overlay the latest monthly INSPIRE freehold polygons against the site/search polygon.','Flag geometry gaps only as possible registration gaps.','Cross-check title/UPRN/freehold evidence from licensed providers when configured.','For unresolved land, generate a SIM search plan/request and retain the result as evidence.']}

@app.get('/api/v1/intelligence/source-health')
async def source_health():
 checks=[('planning-data','https://www.planning.data.gov.uk/'),('postcodes','https://api.postcodes.io/postcodes/SW1A%201AA'),('ea-flood','https://environment.data.gov.uk/flood-monitoring/id/floods?lat=51.5&long=-0.12&dist=1')]
 async def one(name,url):
  try:
   async with httpx.AsyncClient(timeout=12,follow_redirects=True) as c:r=await c.get(url);return {'source':name,'status':'available' if r.status_code<500 else 'degraded','http_status':r.status_code}
  except Exception as e:return {'source':name,'status':'unavailable','error':str(e)}
 rows=await asyncio.gather(*(one(*x) for x in checks));rows.extend([{'source':'os-data-hub','status':'configured' if OS_DATA_HUB_API_KEY else 'not_configured'},{'source':'google-maps','status':'configured' if GOOGLE_MAPS_BROWSER_KEY else 'not_configured'}]);return {'checks':rows,'checked_at':now(),'rule':'An upstream outage is different from a verified absence of evidence.'}
