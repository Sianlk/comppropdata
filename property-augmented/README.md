# Property Development, Augmented — independent production platform

This folder is the standalone, GitHub-owned version of **Property Development, Augmented**. Lovable is optional: it can be used as a visual editor/preview, but the production architecture does not require Lovable Cloud or Lovable AI.

## What is included

### Front end — Next.js
Public authority/SEO site plus an authenticated-style workspace UI for:

- SITE Intelligence
- Planning Intelligence & evidence matrices
- Development Appraisal / Residual Land Value / finance calculators
- Quote Comparator
- Risk Register
- Variation Tracker
- Decision Log
- Document Intelligence
- Consultant Brief Builder
- Weekly Reporting
- PROVE Evidence Room
- Multi-format Report Studio
- Deep Research Agent
- AI Project Assistant with specialist modes
- SEO & Authority Studio
- Product library / consultancy funnel

### Back end — FastAPI
Independent REST API with PostgreSQL/SQLite persistence, JWT auth, upload/document extraction, AI provider abstraction, report generation, payments and live-data adapters.

### Live/authoritative data adapters

1. **Planning Data API** — `planning.data.gov.uk` constraints and planning/housing entities. The government service is beta, so the UI/API carries coverage/completeness caveats.
2. **HM Land Registry Price Paid Data** — linked-data SPARQL by postcode with Crown copyright/OGL attribution and a clear 'not a valuation' limitation.
3. **Environment Agency flood monitoring** — nearby real-time warnings/alerts; not safety-critical advice.
4. **GOV.UK Search API** — policy/document discovery; current wording must be verified in authoritative documents.
5. **Companies House API** — optional API key for live company search.
6. **Energy performance data** — configurable current EPC API adapter because the legacy Open Data Communities endpoint has been retired/replaced.
7. **Google Trends RSS** — trending topics only; never presented as keyword volume.
8. **Semrush** — optional measured keyword adapter. Search volume/difficulty is deliberately null unless measured data is connected.
9. **User documents** — PDF, DOCX, XLSX, CSV, TXT/JSON extraction with SHA-256 evidence identifiers.

## AI controls

The API ships specialist modes:

- Site Analyst
- Planning Evidence Analyst
- Procurement Analyst
- Project Controls Analyst
- Report Writer
- SEO Strategist

Every system prompt explicitly separates facts, assumptions and professional judgement. Missing evidence must be labelled **not established**. Variations must not be marked approved unless approval is evidenced.

## Product/report assets

`assets/` contains the built lead magnet, AI Property Developer OS spreadsheet, playbook and book manuscript. The API can generate new PDF, DOCX, XLSX, CSV and JSON reports.

## Local start

```bash
cp .env.example .env
# change JWT_SECRET and database password
# add OPENAI_API_KEY for live AI

docker compose up --build
```

Web: `http://localhost:3000`  
API docs: `http://localhost:8080/docs`  
Health: `http://localhost:8080/health`

## Production deployment without Lovable

The two services are ordinary containers. Deploy the **web** image to Vercel, Cloudflare Container/Workers-compatible hosting, DigitalOcean, Railway, Render, Fly.io or Kubernetes. Deploy the **api** image anywhere supporting Docker plus PostgreSQL. Configure `NEXT_PUBLIC_API_BASE_URL` to the public API origin.

For the existing Sianlk infrastructure, the simplest path is DigitalOcean App Platform for API/Postgres and Vercel or DigitalOcean for Next.js. GitHub remains the source of truth.

## Required one-time production credentials

The code works without Lovable, but external services cannot be authenticated by source code alone. Configure only the providers you intend to use:

- `OPENAI_API_KEY`
- `COMPANIES_HOUSE_API_KEY`
- current EPC API credentials/endpoint
- Stripe secret, webhook secret and price IDs
- optional Semrush credentials
- domain/DNS
- analytics/Search Console ownership

Do **not** commit these secrets.

## SEO architecture

The Next.js site includes unique metadata, canonical URLs, sitemap, robots directives, crawlable internal links and `SoftwareApplication`/`WebSite` JSON-LD. Tool pages are built around high-intent UK clusters such as planning application AI, planning constraints checker, property development appraisal calculator, construction quote comparison and construction workflow automation.

Google Search Central guidance should remain the source of truth: useful crawlable content, descriptive titles, semantic links, sitemaps and structured data help Google understand the site but do not guarantee rankings.

## Existing ecosystem

This platform can sit above and link into:

- `Sianlk/buildquote` — smart construction quoting
- `Sianlk/comppropdata` — property intelligence / comparable data

Those products can later be exposed as internal services behind the same API gateway.
