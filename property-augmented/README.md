# Property Development, Augmented — independent production platform

This folder is the standalone, GitHub-owned implementation of **Property Development, Augmented**. The production architecture does not require Lovable Cloud or Lovable AI.

## Core design

**SITE → BUILD → PROVE** is implemented as an evidence-first operating system rather than a generic chatbot. The platform combines deterministic development calculations, current public/paid data adapters, specialist AI agents, secure project documents, project-control registers and a human-reviewed evidence graph.

The distinctive rule is simple: **if evidence is missing, record “not established” rather than manufacture confidence.**

## Product surface

The Next.js workspace contains:

- Specialist Agent Studio with Development Director, Site, Planning Evidence, Commercial, Procurement, Project Controls, Document Auditor, Consultant Brief, Reporting, SEO/Authority, Deep Research and Evidence Challenger agents
- SITE Intelligence and current Policy & Standards Library
- Development Appraisal, Residual Land Value, finance and deterministic 49-case Scenario Lab
- Planning Intelligence and consultant briefing
- Quote Comparator, Risk Register, Variation Tracker, Decision Log and Weekly Reporting
- private Document Vault with ownership, retention, container limits, prompt-injection flags and SHA-256 provenance
- Evidence Review Room with claim-by-claim human verification/contestation
- fingerprinted Project Decision Pack PDF/JSON exports
- authenticated state-change Audit Trail
- Report Studio, Deep Research, SEO/Authority and products/consultancy workflows

## Evidence architecture

Specialist AI runs persist:

- model/run identifier
- input and output SHA-256 fingerprints
- consulted web-source metadata where applicable
- instruction-injection/security flags
- review state
- structured findings classified as `confirmed_fact`, `assumption`, `professional_opinion`, `inference`, `decision` or `not_established`
- confidence, materiality, source refs and verification action for each claim

AI outputs remain working material until human reviewed. Evidence health is deliberately a **review state**, never a fake probability of planning or commercial success.

## Private AI and documents

Private project AI uses the OpenAI Responses API with provider-side response storage explicitly requested as disabled (`store: false`). Uploaded/web/project material is treated as **untrusted evidence**, not instructions.

The secure document flow supports PDF, DOCX, XLSX/XLSM, CSV, TXT, Markdown and JSON with owner/project scoping, file-size limits, Office-container expansion checks, PDF limits, retention dates, deletion, SHA-256 identifiers and server-side Document Auditor analysis. Spreadsheet macros are never executed.

## Data/source layer

Adapters currently include:

1. Planning Data API — beta coverage caveats remain visible.
2. HM Land Registry Price Paid Data — source-backed comparables, explicitly not a valuation.
3. Environment Agency flood monitoring.
4. GOV.UK policy discovery.
5. Companies House API when configured.
6. Current EPC API adapter when configured.
7. Google Trends RSS — trends only, never fabricated keyword volume.
8. Semrush measured-keyword adapter when configured.
9. Google Search Console when configured.
10. OpenAI live web research with consulted-source metadata.

The Policy & Standards Library includes current national planning/building sources but explicitly refuses to treat national discovery as proof of a site's complete Local Plan, SPD, validation, CIL or authority-specific position.

## Security/operations

- strong JWT secret required in production
- owner-scoped projects/documents/evidence
- same-origin Next.js `/backend` gateway by default
- CSP, HSTS, frame denial, nosniff, referrer and permissions policies
- request IDs and server timing
- baseline compute/auth rate limiting (edge/WAF distributed controls still recommended)
- authenticated mutation audit events without request bodies/secrets
- password reset flow
- Stripe webhook entitlement model
- production readiness endpoint that blocks “ready” status when required credentials/legal identity are missing
- dedicated GitHub Actions CI for Python compile/routes/tests/audit and frontend lint/type/build/audit
- production dependency vulnerability audits fail the build; vulnerabilities are not waived merely to obtain a green badge

## Run locally

```bash
cp .env.example .env
# set a strong database password + JWT secret
# add any provider credentials you intend to test

docker compose up --build
```

Web: `http://localhost:3000`  
API docs: `http://localhost:8080/docs`  
Health: `http://localhost:8080/health`

The browser uses `/backend`; the Next.js server proxies it to `PDA_API_ORIGIN`. This allows the same frontend image to move between hosting providers without baking a private API origin into browser JavaScript.

## Production launch gate

Before a paid/public launch, `/api/v1/system/readiness` must report `ready`. Required production items include:

- non-SQLite persistent database
- strong JWT secret
- HTTPS site + production CORS
- persistent document storage
- OpenAI key for AI features
- Stripe secret/webhook + configured product/service price IDs
- transactional email + notification address
- legal operator identity and privacy contact

Optional adapters such as Companies House, EPC, Search Console, Semrush and analytics report separately and do not masquerade as configured.

## Deployment

The web and API are ordinary containers. GitHub remains the source of truth. A typical deployment is:

- Next.js web container (or compatible Node host)
- FastAPI container
- managed PostgreSQL
- persistent/object storage for project documents
- TLS/WAF/edge rate limiting
- secrets supplied by the host, never committed

Set `PDA_API_ORIGIN` on the **web server/container** to the internal/public API origin. Keep the browser on the default `/backend` route unless there is a deliberate reason to expose a separate CORS API origin.

## Commercial/provider credentials

Source code cannot create third-party authority on its own. Production owners must supply and manage the intended OpenAI, Stripe, email, Companies House/EPC, SEO/Search Console, analytics, domain/DNS and hosting credentials.

## Legal/trust

Public `/privacy`, `/terms` and `/trust` pages are implemented. Paid launch is blocked by the readiness endpoint until `LEGAL_OPERATOR_NAME` and `PRIVACY_CONTACT_EMAIL` are configured. The operator should still obtain legal review appropriate to the exact entity, customer type, insurance, service scope and commercial contract before accepting material paid engagements.
