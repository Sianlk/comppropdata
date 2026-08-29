export const API_BASE=(process.env.NEXT_PUBLIC_API_BASE_URL||'').replace(/\/$/,'');

export const endpoints={
  health:'/health',status:'/api/v1/system/status',sources:'/api/v1/data/sources',site:'/api/v1/site/intelligence/full',
  analyse:'/api/v1/ai/analyse',deepResearch:'/api/v1/research/web-deep',policyLibrary:'/api/v1/policy/library',policySearch:'/api/v1/policy/search',appraisal:'/api/v1/calculators/appraisal',
  residual:'/api/v1/calculators/residual',finance:'/api/v1/calculators/finance',quotes:'/api/v1/quotes/compare',
  upload:'/api/v1/documents/upload',report:'/api/v1/reports/generate',seo:'/api/v1/seo/strategy',trends:'/api/v1/seo/trending-now',
  measuredKeywords:'/api/v1/seo/measured-keywords',searchConsole:'/api/v1/seo/search-console',projects:'/api/v1/projects',
  login:'/api/v1/auth/login',register:'/api/v1/auth/register',me:'/api/v1/auth/me',forgotPassword:'/api/v1/auth/forgot-password',resetPassword:'/api/v1/auth/reset-password',products:'/api/v1/products',
  leads:'/api/v1/leads/capture',consultancy:'/api/v1/consultancy/submit',checkout:'/api/v1/payments/checkout',
  siteTriage:'/api/v1/resources/site-triage.pdf',osGeneratedDownload:'/api/v1/products/ai-property-developer-os/generated-download'
} as const;

type Options=RequestInit&{timeoutMs?:number};
export class ApiError extends Error{status:number;body:string;constructor(status:number,body:string){super(body||`Request failed ${status}`);this.status=status;this.body=body}}
export const apiConfigured=()=>Boolean(API_BASE);
export const absoluteApi=(path:string)=>path.startsWith('http')?path:`${API_BASE}${path}`;
export function getToken(){if(typeof window==='undefined')return null;return sessionStorage.getItem('pda_token')||localStorage.getItem('pda_token')}
export function setToken(value:string){if(typeof window==='undefined')return;sessionStorage.setItem('pda_token',value);localStorage.removeItem('pda_token')}
export function clearToken(){if(typeof window==='undefined')return;sessionStorage.removeItem('pda_token');localStorage.removeItem('pda_token')}

export async function api<T=any>(path:string,options:Options={}):Promise<T>{
  if(!API_BASE)throw new Error('Live API is not configured. Set NEXT_PUBLIC_API_BASE_URL.');
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),options.timeoutMs??45000);const token=getToken();
  try{
    const isForm=typeof FormData!=='undefined'&&options.body instanceof FormData;
    const res=await fetch(`${API_BASE}${path}`,{...options,signal:controller.signal,headers:{...(isForm?{}:{'Content-Type':'application/json'}),...(token?{Authorization:`Bearer ${token}`}:{}) ,...(options.headers||{})}});
    if(!res.ok){const text=await res.text();throw new ApiError(res.status,text||`Request failed ${res.status}`)}
    const ct=res.headers.get('content-type')||'';if(ct.includes('application/json'))return res.json();return(await res.blob())as T;
  }finally{clearTimeout(timeout)}
}

export async function apiDownload(path:string,options:Options={},filename='property-augmented-report'){
  const blob=await api<Blob>(path,options);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
