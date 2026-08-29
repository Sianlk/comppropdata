/** @type {import('next').NextConfig} */
const apiTarget=process.env.API_INTERNAL_URL||process.env.NEXT_PUBLIC_API_BASE_URL||'http://api:8080';
const csp=["default-src 'self'","base-uri 'self'","object-src 'none'","frame-ancestors 'none'","form-action 'self' https://checkout.stripe.com","img-src 'self' data: https:","font-src 'self' data:","style-src 'self' 'unsafe-inline'","script-src 'self' 'unsafe-inline'","connect-src 'self'","upgrade-insecure-requests"].join('; ');
const securityHeaders=[{key:'Content-Security-Policy',value:csp},{key:'Strict-Transport-Security',value:'max-age=31536000; includeSubDomains'},{key:'X-Content-Type-Options',value:'nosniff'},{key:'X-Frame-Options',value:'DENY'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},{key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=()'},{key:'Cross-Origin-Opener-Policy',value:'same-origin'}];
const nextConfig={output:'standalone',poweredByHeader:false,async rewrites(){return[{source:'/backend/:path*',destination:`${apiTarget}/:path*`}]},async headers(){return[{source:'/(.*)',headers:securityHeaders}]}};
export default nextConfig;
