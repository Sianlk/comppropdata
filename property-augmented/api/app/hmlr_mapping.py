from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException, Query
from fastapi.responses import Response

from .bootstrap import app

HMLR_INSPIRE_WMS='https://inspire.landregistry.gov.uk/inspire/ows'
_LAYER: str | None = None

async def _request(params:dict,timeout:int=60):
    async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as client:
        response=await client.get(HMLR_INSPIRE_WMS,params=params)
        response.raise_for_status()
        return response

async def _layer_name()->str:
    global _LAYER
    if _LAYER:return _LAYER
    try:
        response=await _request({'service':'WMS','request':'GetCapabilities'})
        root=ET.fromstring(response.content)
        candidates=[]
        for node in root.iter():
            if node.tag.endswith('Layer'):
                name=None;title=''
                for child in list(node):
                    if child.tag.endswith('Name') and child.text:name=child.text.strip()
                    elif child.tag.endswith('Title') and child.text:title=child.text.strip()
                if name:candidates.append((name,title))
        if not candidates:raise ValueError('No named WMS layer')
        preferred=next((name for name,title in candidates if 'index' in title.lower() or 'polygon' in title.lower() or 'inspire' in title.lower()),None)
        _LAYER=preferred or candidates[-1][0]
        return _LAYER
    except Exception as exc:
        raise HTTPException(502,'HM Land Registry INSPIRE map service did not expose a usable layer') from exc

@app.get('/api/v1/maps/hmlr-inspire.png')
async def hmlr_inspire_map(easting:float,northing:float,radius_m:int=Query(default=250,ge=25,le=2000)):
    layer=await _layer_name();r=float(radius_m)
    common={'service':'WMS','request':'GetMap','layers':layer,'styles':'','bbox':f'{easting-r},{northing-r},{easting+r},{northing+r}','width':768,'height':768,'format':'image/png','transparent':'true'}
    last_error=None
    for version,crs_key in [('1.3.0','crs'),('1.1.1','srs')]:
        try:
            response=await _request({**common,'version':version,crs_key:'EPSG:27700'})
            content_type=response.headers.get('content-type','')
            if 'image' not in content_type.lower() and not response.content.startswith(b'\x89PNG'):
                raise ValueError('WMS did not return an image')
            return Response(content=response.content,media_type='image/png',headers={'Cache-Control':'private, max-age=3600','X-Data-Source':'HM Land Registry INSPIRE Index Polygons','X-Evidence-Limitation':'Indicative registered freehold screen; absence does not prove unregistered land'})
        except Exception as exc:last_error=exc
    raise HTTPException(502,f'HM Land Registry INSPIRE map unavailable: {last_error}')
