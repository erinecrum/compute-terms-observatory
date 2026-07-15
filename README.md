# Compute Contract Terms Observatory

A public observatory of the **published** legal terms of cloud and GPU compute
providers. It fetches and permanently archives each provider's public terms of
service, SLAs, and acceptable use policies; extracts a structured set of legally
significant terms from each; and publishes a comparison of what every provider's
terms say side by side, plus a feed of what changed over time.

Built for technology and infrastructure attorneys, founders signing compute
deals, and analysts. It answers *"what do compute providers' published terms
actually say, how do they compare, and what changed"* — using only public
documents. **It states what documents say. It never advises or recommends.**

---

## ⚖️ Disclaimer

**This is an informational comparison of published documents, not legal advice.**
It describes and compares what public documents say, with citations to the source
document and section. It does not recommend providers, rate them, or tell you what
to do. Provider documents change, and automated extraction can be wrong or stale.
**Always review the current source documents yourself** before relying on anything
here. Nothing in this repository or on the site creates an attorney–client
relationship.

---

## What it covers (v1)

**8 providers.** Hyperscalers: AWS, Microsoft Azure, Google Cloud. GPU-focused:
CoreWeave, Lambda, Crusoe, RunPod, Vast.ai.

**10 term dimensions**, each extracted with a value, a confidence level, and a
citation: availability definition · credit regime · claim mechanics · SLA
exclusions · capacity & reservation terms · data use & AI training · suspension
rights · termination · unilateral modification · governing law & disputes.

### How to read the site

- **Matrix** (`index.html`) — providers as columns, the 10 dimensions as rows.
  Click any cell for the full value, the quoted citation, a link to the source
  document, the fetch date, and a model-confidence indicator. Filter by provider
  or dimension.
- **Provider pages** — every term for one provider with citations and source
  links, the documents archived (with fetch date and version hash), and that
  provider's change history.
- **Change feed** (`changes.html`) — the heartbeat: detected document changes in
  reverse-chronological order, with short before/after excerpts.
- **About** — methodology, coverage, and the disclaimer.

## Design principles (non-negotiable)

1. **Archival discipline is the product.** Every fetched document version is
   preserved forever under `snapshots/<provider>/<slug>/<timestamp>.{html|pdf,txt,json}`,
   timestamped and content-hashed, committed to git, append-only. Nothing is
   overwritten. The versioned corpus is the long-term asset.
2. **Public data only.** Only published documents at public URLs. No login-gated
   content, no user submissions, no confidential inputs anywhere.
3. **Descriptive, never advisory.** Every generated value describes what a
   document says, with a citation. No recommendations, no risk ratings.
4. **Everything traceable.** Each value stores its source URL, fetch date, and
   document version hash, plus the quoted basis. Values that can't be confidently
   supported are recorded as **"not specified"** or **"unclear"** — never guessed.

### The "not published" rule

Some terms are negotiated privately and never published — e.g. the Microsoft
Azure Consumption Commitment (MACC), the AWS Enterprise Discount Program (EDP),
and Google Cloud committed-use discounts. These are recorded under the
capacity & reservation dimension as **"negotiated, not published"** with a
citation to the public page describing the program's existence (see
[`commitment_programs.yaml`](commitment_programs.yaml)). The same rule applies to
any document we cannot find at a public URL: record it as not published, cite the
public evidence, and never substitute a third-party copy.

## How it works

Python, minimal dependencies. The pipeline is data-driven — **adding a provider
or document is a [`registry.yaml`](registry.yaml) edit, not a code change.**

```
registry.yaml ──▶ fetcher ──▶ snapshot store ──▶ differ ──▶ change feed
   (URLs)         (HTML/PDF)   (raw + text +      (localized
                               hash, append-only)  old/new excerpts)
                                     │
                                     ▼
                              extractor (Claude/Opus, 10-term schema,
                                     │     one JSON record per dimension,
                                     │     full provenance, never guesses)
                                     ▼
                    overrides/<provider>.yaml  (human-verified corrections,
                                     │          survive re-extraction)
                                     ▼
                              dataset builder ──▶ static site (matrix,
                            (data/dataset.json)     provider pages, change feed)
```

Modules live in `observatory/`: `registry`, `fetcher`, `snapshot`, `differ`,
`schema`, `extractor`, `overrides`, `dataset`, `site`.

### Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY (extraction only)

python main.py run            # fetch → snapshot changed → re-extract changed → build → site
# or step by step:
python main.py fetch          # archive all sources (no API key needed)
python main.py changes        # show detected changes between snapshots
python main.py extract        # run the Claude extraction (needs API key)
python main.py build          # assemble data/dataset.json
python main.py site           # render the static site into site/
```

The fetch / snapshot / diff layers need **no API key** — the corpus can be built
and updated with no secret present. Only extraction calls the Claude API.

## Secrets

`ANTHROPIC_API_KEY` lives in a local `.env` (gitignored, never committed). The
weekly GitHub Action reads it from a repository secret of the same name. See
[`.env.example`](.env.example). No key string appears anywhere in the repo.

## Automation

[`.github/workflows/weekly.yml`](.github/workflows/weekly.yml) runs every Monday
(and on demand): fetch all sources, snapshot anything changed, re-extract only the
changed providers, rebuild the dataset and site, commit the corpus, and deploy the
site to GitHub Pages.

## Going public (one-time steps)

This repo starts **private** and is built as if already public (no secrets, no
confidential inputs). To publish later:

1. Add the `ANTHROPIC_API_KEY` repository secret (Settings → Secrets and variables → Actions).
2. Enable GitHub Pages with **Source: GitHub Actions** (Settings → Pages). Private-repo
   Pages needs a plan that supports it, or make the repo public first.
3. Flip the repo to public when ready.

## Out of scope for v1

Negotiated-terms data, user accounts/submissions, email subscriptions, provider
ratings/scores, and more than 8 providers. The code is structured so providers
and features can be added without rework.
