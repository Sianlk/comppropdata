from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .bootstrap import app


def _book_path() -> Path:
    candidates = [
        Path('/content/book.json'),
        Path(__file__).resolve().parents[2] / 'web' / 'content' / 'book.json',
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError('Published book source is not available in this deployment')


def _load_book() -> dict:
    return json.loads(_book_path().read_text(encoding='utf-8'))


def _book_pdf() -> bytes:
    book = _load_book()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm, topMargin=18*mm, bottomMargin=18*mm, title=book['title'], author='Property Development, Augmented Research Team')
    styles = getSampleStyleSheet()
    title = ParagraphStyle('BookTitle', parent=styles['Title'], fontName='Times-Bold', fontSize=30, leading=32, textColor=colors.HexColor('#171714'), spaceAfter=12)
    subtitle = ParagraphStyle('BookSubtitle', parent=styles['BodyText'], fontName='Helvetica', fontSize=12, leading=18, textColor=colors.HexColor('#5A554D'), spaceAfter=14)
    chapter = ParagraphStyle('Chapter', parent=styles['Heading1'], fontName='Times-Bold', fontSize=23, leading=26, textColor=colors.HexColor('#171714'), spaceAfter=10)
    heading = ParagraphStyle('Heading', parent=styles['Heading2'], fontName='Times-Bold', fontSize=15, leading=19, textColor=colors.HexColor('#3B332A'), spaceBefore=9, spaceAfter=6)
    body = ParagraphStyle('Body', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.7, leading=15, textColor=colors.HexColor('#282622'), spaceAfter=7)
    meta = ParagraphStyle('Meta', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8, leading=12, textColor=colors.HexColor('#9A744B'), spaceAfter=7)
    note = ParagraphStyle('Note', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.4, leading=13, textColor=colors.HexColor('#69635C'), backColor=colors.HexColor('#F1ECE4'), borderPadding=7, spaceBefore=8, spaceAfter=8)
    story = [
        Spacer(1, 25*mm),
        Paragraph(book['title'].upper(), meta),
        Paragraph(book['title'], title),
        Paragraph(book['subtitle'], subtitle),
        Paragraph(f"{book['edition']} · Published {book['published']} · Reviewed {book['reviewed']}", meta),
        Spacer(1, 8*mm),
        Paragraph(book['description'], subtitle),
        Paragraph('INPUT → STRUCTURE → ANALYSE → VERIFY → DECIDE → LOG', note),
        PageBreak(),
        Paragraph('Contents', chapter),
    ]
    for c in book['chapters']:
        story.append(Paragraph(f"{c['number']}. {c['title']}", body))
    story.append(PageBreak())
    for idx, c in enumerate(book['chapters']):
        story.extend([
            Paragraph(f"CHAPTER {c['number']}", meta),
            Paragraph(c['title'], chapter),
            Paragraph(c['standfirst'], subtitle),
        ])
        for section in c['sections']:
            story.append(Paragraph(section['heading'], heading))
            for paragraph in section['body']:
                story.append(Paragraph(paragraph, body))
        story.append(Paragraph('Evidence rule: verify live planning policy, title, legal, technical, cost, tax, finance and safety matters against the authoritative source and the appropriate qualified professional or statutory authority where required.', note))
        if idx < len(book['chapters'])-1:
            story.append(PageBreak())
    story.extend([PageBreak(), Paragraph('Primary sources and live-reference starting points', chapter)])
    for source in book.get('sources', []):
        story.append(Paragraph(f"<b>{source['name']}</b><br/>{source['url']}", body))
    story.append(Paragraph('This digital edition is versioned because planning policy, data services, regulation and provider contracts change. The online edition should be checked for the latest review date.', note))
    doc.build(story)
    return buf.getvalue()


@app.get('/api/v1/resources/property-development-augmented-book.pdf')
def book_pdf_resource():
    raw = _book_pdf()
    return StreamingResponse(io.BytesIO(raw), media_type='application/pdf', headers={'Content-Disposition':'attachment; filename="property-development-augmented-first-digital-edition.pdf"','Cache-Control':'public, max-age=3600'})


@app.get('/api/v1/resources/book')
def book_json_resource():
    book = _load_book()
    return {'title':book['title'],'subtitle':book['subtitle'],'edition':book['edition'],'published':book['published'],'reviewed':book['reviewed'],'chapter_count':len(book['chapters']),'chapters':[{'number':c['number'],'slug':c['slug'],'title':c['title'],'standfirst':c['standfirst']} for c in book['chapters']]}
