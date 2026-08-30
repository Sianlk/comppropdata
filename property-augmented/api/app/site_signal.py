from __future__ import annotations

import io
import json

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from .bootstrap import PUBLIC_API_URL, _brevo_send, _valid_email, app
from . import full_stack as stack


class SiteSignalLead(BaseModel):
    email: str
    name: str = ''
    marketing_consent: bool = False
    source: str = 'site-signal'


def _site_signal_pdf() -> bytes:
    prompts = [
        ('SITE', 'Can you clearly identify the property/site and the land you believe is included?'),
        ('USE', 'What is the present use — and do you have evidence for it rather than an assumption?'),
        ('PLANNING', 'What single planning fact would most change whether you investigate this opportunity further?'),
        ('CONSTRAINT', 'Which obvious issue could kill or reshape the idea: access, heritage, flood, ecology, neighbours, title or existing building condition?'),
        ('NEXT STEP', 'What is the cheapest reliable check that would remove the biggest uncertainty?'),
    ]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('title', parent=styles['Title'], fontName='Times-Bold', fontSize=26, leading=29, textColor=colors.HexColor('#171714'), spaceAfter=9)
    sub = ParagraphStyle('sub', parent=styles['BodyText'], fontSize=11, leading=16, textColor=colors.HexColor('#6A655E'), spaceAfter=12)
    label = ParagraphStyle('label', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.HexColor('#9A744B'), spaceBefore=8, spaceAfter=3)
    body = ParagraphStyle('body', parent=styles['BodyText'], fontSize=10, leading=15, textColor=colors.HexColor('#282622'), spaceAfter=8)
    note = ParagraphStyle('note', parent=styles['BodyText'], fontSize=9, leading=14, textColor=colors.HexColor('#5E5850'), backColor=colors.HexColor('#F1ECE4'), borderPadding=8, spaceBefore=10)
    story = [
        Paragraph('THE 5-MINUTE DEVELOPMENT SITE SIGNAL', title),
        Paragraph('Five questions to decide whether a site deserves deeper investigation — without giving away the full intelligence workflow.', sub),
        Paragraph('This is a screening prompt, not a planning search, title check, appraisal, sold-price report, policy review or development recommendation.', note),
        Spacer(1, 3*mm),
    ]
    for i, (kind, question) in enumerate(prompts, 1):
        story.extend([
            Paragraph(f'{i:02d} · {kind}', label),
            Paragraph(question, body),
            Paragraph('Working answer: _______________________________________________________________<br/>Evidence/source: _________________________________________________________________', body),
        ])
    story.extend([
        Spacer(1, 4*mm),
        Paragraph('<b>Stop here if the opportunity still depends on guesses.</b> The full platform is designed to retrieve the live planning, mapping, title, sold-price, cost and policy evidence behind those guesses from the postcode/address.', note),
        Paragraph('Educational screening material only. Professional/statutory evidence remains with the appropriate source and competent adviser.', sub),
    ])
    doc.build(story)
    return buf.getvalue()


@app.middleware('http')
async def retire_legacy_site_triage(request: Request, call_next):
    if request.url.path == '/api/v1/resources/site-triage.pdf':
        return RedirectResponse('/api/v1/resources/site-signal.pdf', status_code=307)
    return await call_next(request)


@app.get('/api/v1/resources/site-signal.pdf')
def site_signal_pdf():
    raw = _site_signal_pdf()
    return StreamingResponse(io.BytesIO(raw), media_type='application/pdf', headers={'Content-Disposition':'attachment; filename="5-minute-development-site-signal.pdf"','Cache-Control':'public, max-age=3600'})


@app.post('/api/v1/leads/site-signal')
async def site_signal_lead(r: SiteSignalLead, s: Session = Depends(stack.db)):
    email = _valid_email(r.email)
    lead = stack.Lead(email=email, name=r.name.strip(), source=r.source, consent=r.marketing_consent, payload_json=json.dumps({'requested_resource':'site-signal'}))
    s.add(lead); s.commit(); s.refresh(lead)
    path = '/api/v1/resources/site-signal.pdf'
    delivery = await _brevo_send(email, 'Your 5-Minute Development Site Signal', f'<p>Your Site Signal is ready.</p><p><a href="{PUBLIC_API_URL}{path}">Download it here</a>.</p><p>The full platform goes materially deeper: live local/national policy, mapping, planning history, appeals, title, market, costs and development appraisal from the site address.</p>')
    return {'id':lead.id,'status':'captured','marketing_consent':r.marketing_consent,'download_url':path,'email_delivery':delivery}
