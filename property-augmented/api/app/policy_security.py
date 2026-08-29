import os
import time
import uuid
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from .bootstrap import app
from . import full_stack as stack

ENV=os.getenv('ENV','development').lower()
_BUCKETS:dict[str,deque[float]]=defaultdict(deque)

def _rate_limited(key:str,limit:int,window_seconds:int=60)->bool:
    now=time.monotonic();bucket=_BUCKETS[key]
    while bucket and bucket[0] < now-window_seconds:bucket.popleft()
    if len(bucket)>=limit:return True
    bucket.append(now);return False

@app.middleware('http')
async def security_observability_guard(request:Request,call_next):
    request_id=request.headers.get('x-request-id','')
    if not request_id or len(request_id)>100:request_id=str(uuid.uuid4())
    request.state.request_id=request_id
    started=time.perf_counter();path=request.url.path
    if ENV=='production':
        client=request.client.host if request.client else 'unknown'
        if path.startswith('/api/v1/auth/') and _rate_limited(f'auth:{client}',20):
            return JSONResponse({'detail':'Too many authentication requests','request_id':request_id},status_code=429,headers={'Retry-After':'60','X-Request-ID':request_id})
        expensive=('/api/v1/ai/','/api/v1/research/','/api/v1/agents/','/api/v1/policy/search','/api/v1/seo/')
        if path.startswith(expensive) and _rate_limited(f'ai:{client}',40):
            return JSONResponse({'detail':'Rate limit exceeded for compute-intensive endpoints','request_id':request_id},status_code=429,headers={'Retry-After':'60','X-Request-ID':request_id})
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Opener-Policy']='same-origin'
    response.headers['Server-Timing']=f'app;dur={(time.perf_counter()-started)*1000:.1f}'
    if ENV=='production':response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

@app.middleware('http')
async def policy_research_auth_guard(request:Request,call_next):
    # Public library remains indexable; live AI-backed policy research consumes provider resources and requires an account in production.
    if ENV=='production' and request.url.path=='/api/v1/policy/search':
        auth=request.headers.get('authorization','')
        if not auth.lower().startswith('bearer '):
            return JSONResponse({'detail':'Authentication required'},status_code=401)
        try:stack.decode(auth.split(' ',1)[1])
        except HTTPException:return JSONResponse({'detail':'Invalid or expired token'},status_code=401)
    return await call_next(request)

@app.get('/api/v1/system/security-posture')
def security_posture():
    return {'environment':ENV,'controls':{'strong_production_jwt_required':True,'compute_authentication':True,'rate_limit_baseline':True,'request_ids':True,'hsts_in_production':True,'security_headers':True,'ai_source_material_treated_as_untrusted':True,'agent_outputs_require_human_review':True},'note':'Application limits are a baseline. Production should also enforce distributed rate limiting/WAF controls at the edge.'}
