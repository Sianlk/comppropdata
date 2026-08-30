# Product assets

Production release assets are intentionally kept out of source-control commits until the commercial distribution decision is made. Provision these filenames into `/assets` (or `PRODUCT_ASSET_DIR`) from the production launch pack:

- `30-minute-ai-site-triage.pdf`
- `ai-property-developer-os.xlsx`
- `ai-property-developer-os-playbook.docx`
- `property-development-augmented-book.docx`

The source-controlled API refuses a gated download if its file is not provisioned; it never substitutes a fake asset.
