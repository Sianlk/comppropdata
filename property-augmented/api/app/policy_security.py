import os
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from .bootstrap import app
from . import full_stack as stack

ENV=os.getenv('ENV','development').lower()

@app.middleware('http')
async def policy_research_auth_guard(request:Request,call_next):
    # Policy library is public/indexable data; live AI-backed policy research consumes provider resources and requires an account in production.
    if ENV=='production' and request.url.path=='/api/v1/policy/search':
        auth=request.headers.get('authorization','')
        if not auth.lower().startswith('bearer '):
            return JSONResponse({'detail':'Authentication required'},status_code=401)
        try:
            stack.decode(auth.split(' ',1)[1])
        except HTTPException:
            return JSONResponse({'detail':'Invalid or expired token'},status_code=401)
    return await call_next(request)
