# Production data-source matrix

| Source | Use | Limitation |
|---|---|---|
| Planning Data (MHCLG) | Planning constraints/entities | Beta; coverage/completeness varies by dataset/authority. |
| HM Land Registry Price Paid Data | Transaction evidence/comparables | Registration lag and exclusions; not a valuation; attribution/licence must be observed. |
| Environment Agency Flood Monitoring | Nearby live warnings/alerts | No guaranteed SLA; not safety-critical advice. |
| GOV.UK | Policy/document discovery | Search result is not a substitute for verifying the current authoritative document. |
| Companies House API | Company identity/filings | API key/rate limits; filings require context. |
| Energy performance data | EPC research | Current service requires account/API setup; open data may contain expired/replaced certificates. |
| Postcodes.io | Postcode geocoding | Postcode centroid, not surveyed site geometry. |
| Google Trends RSS | Current trending topics | Not keyword search-volume data. |
| Optional Semrush | Measured SEO metrics | Display volume/difficulty only when returned by provider. |
| User uploads | Project-specific evidence | Extraction depends on document quality; image-only files require multimodal processing. |

Official references: https://www.planning.data.gov.uk/docs ; https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads ; https://environment.data.gov.uk/flood-monitoring/doc/reference ; https://developer.company-information.service.gov.uk/ ; https://get-energy-performance-data.communities.gov.uk/
