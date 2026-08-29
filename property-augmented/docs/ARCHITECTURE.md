# Architecture

Production request path:

`Browser / Next.js -> HTTPS REST -> FastAPI -> PostgreSQL/uploads + AI provider + authoritative/public data adapters`

Lovable is intentionally **not** on the production request path. It may remain a visual editor/preview only.

## Data adapters

Planning Data; HM Land Registry Price Paid Data; Environment Agency flood monitoring; GOV.UK policy discovery; Companies House; configurable current EPC data service; Postcodes.io; Google Trends trending RSS; optional measured SEO provider; user-uploaded project documents.

## Trust model

Every material intelligence result should retain provider/source URL or document identifier, retrieval/upload time, caveat/freshness note and a human-review gate. Missing evidence is `not established`. Discussion is not approval and an AI summary must not create approval or professional authority.

## Existing ecosystem

The umbrella platform can integrate the existing `Sianlk/buildquote` quotation product and `Sianlk/comppropdata` property-comparable product behind one future API/account layer.
