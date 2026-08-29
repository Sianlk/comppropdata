from __future__ import annotations
import os
from pathlib import Path
from .bootstrap import app
from . import full_stack as stack
from . import main as core


def _strong_secret(value:str)->bool:return bool(value and len(value)>=32 and 'replace-' not in value.lower() and value!='dev-change-me')
def _https(value:str)->bool:return value.lower().startswith('https://')
def _present(name:str)->bool:return bool(os.getenv(name,'').strip())

@app.get('/api/v1/system/readiness')
def production_readiness():
    env=os.getenv('ENV','development').lower();frontend=os.getenv('NEXT_PUBLIC_SITE_URL',os.getenv('FRONTEND_URL',''));db=os.getenv('DATABASE_URL','');cors=os.getenv('CORS_ORIGINS','');storage=Path(os.getenv('STORAGE_DIR','./storage'))
    required={
        'production_environment':env=='production',
        'strong_jwt_secret':_strong_secret(stack.JWT_SECRET),
        'persistent_database':bool(db) and not db.startswith('sqlite'),
        'https_public_site':_https(frontend),
        'production_cors':bool(cors) and 'localhost' not in cors and '127.0.0.1' not in cors,
        'openai_provider':bool(core.OPENAI_API_KEY),
        'stripe_secret':_present('STRIPE_SECRET_KEY'),
        'stripe_webhook_secret':_present('STRIPE_WEBHOOK_SECRET'),
        'stripe_product_price':_present('STRIPE_PRICE_OS'),
        'stripe_consultancy_price':_present('STRIPE_PRICE_CONSULT'),
        'transactional_email':_present('BREVO_API_KEY') and _present('FROM_EMAIL'),
        'operator_notification_email':_present('NOTIFY_EMAIL'),
        'legal_operator_identity':_present('LEGAL_OPERATOR_NAME'),
        'privacy_contact':_present('PRIVACY_CONTACT_EMAIL'),
        'persistent_storage_configured':str(storage) not in {'storage','./storage'}
    }
    optional={'companies_house':bool(core.COMPANIES_HOUSE_API_KEY),'epc':bool(core.EPC_API_URL),'search_console':_present('GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN') and _present('GOOGLE_SEARCH_CONSOLE_SITE_URL'),'semrush':_present('SEMRUSH_API_KEY'),'analytics':_present('NEXT_PUBLIC_GA4_ID') or _present('NEXT_PUBLIC_POSTHOG_KEY')}
    blockers=[key for key,value in required.items() if not value]
    return {'status':'ready' if not blockers else 'blocked','required':required,'optional':optional,'blockers':blockers,'note':'Ready means the configured production prerequisites are present. It is not a warranty of service availability, legal compliance, data accuracy or commercial performance.'}
