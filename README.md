# Compute Contract Terms Observatory

A public observatory of the **published** legal terms of cloud and GPU compute
providers. It fetches and permanently archives each provider's public terms of
service, SLAs, and acceptable use policies; extracts a structured set of legally
significant terms from each; and publishes a comparison showing what every
provider's terms say side by side, plus a feed of what changed over time.

The audience is technology and infrastructure attorneys, founders signing
compute deals, and analysts.

---

## ⚖️ Disclaimer

**This is an informational comparison of published documents, not legal advice.**
It describes and compares what public documents say, with citations to the source
document and section. It does not recommend providers, rate them, or tell you what
to do. Provider documents change, and automated extraction can be wrong or stale.
**Always review the current source documents yourself** before relying on anything
here. Nothing on this site or in this repository creates an attorney–client
relationship.

---

## What it does (v1)

Covers 8 providers: **AWS, Microsoft Azure, Google Cloud** (hyperscalers) and
**CoreWeave, Lambda, Crusoe, RunPod, Vast.ai** (GPU-focused).

For each provider it archives the public terms/SLA/AUP/AI-terms documents and
extracts a fixed schema of terms (availability definition, credit regime, claim
mechanics, SLA exclusions, capacity/reservation terms, data use & AI training,
suspension rights, termination, unilateral modification, governing law & disputes).

### Design principles

1. **Archival discipline is the product.** Every fetched document version is
   preserved forever with a timestamp under `snapshots/`, committed to git.
   Nothing is overwritten or discarded — the versioned corpus is the long-term asset.
2. **Public data only.** Only published documents at public URLs. No login-gated
   content, no user submissions, no confidential inputs anywhere.
3. **Descriptive, never advisory.** All generated text describes and compares
   what documents say, with citations. No recommendations, no risk ratings.
4. **Everything traceable.** Every extracted data point stores its source URL,
   fetch date, document version hash, and the quoted/paraphrased basis. Values
   that can't be confidently extracted are stored as "not specified" or "unclear".

## Status

🚧 Under construction — being built step by step. See the spec and build order.

## Secrets

The `ANTHROPIC_API_KEY` (used only by the extraction layer) lives in a local
`.env` file, which is gitignored and never committed. Scheduled runs use a GitHub
Actions secret. See [`.env.example`](.env.example).
