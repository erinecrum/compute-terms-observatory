# Project Spec: Compute Contract Terms Observatory (v1)

## What you are building

A public observatory of the published legal terms of cloud and GPU compute providers. It fetches and permanently archives each provider's public terms of service, SLAs, and acceptable use policies, extracts a structured set of legally significant terms from each, and publishes a comparison site showing what every provider's terms say side by side, plus a feed of what changed over time.

The audience is technology and infrastructure attorneys, founders signing compute deals, and analysts. The product answers "what do compute providers' published terms actually say, how do they compare, and what changed" using only public documents. It states what documents say. It never gives advice or recommendations.

I am a practicing technology transactions attorney directing this build, not a professional developer. I previously built a related project (an AWS legal event radar) with a similar architecture: scheduled fetching, snapshots, diffs, a Claude API analysis layer, and a static GitHub Pages site. This is a separate repo but may reuse the same patterns. Explain technical choices briefly and ask me before adding complexity beyond this spec.

## Non-negotiable design principles

1. **Archival discipline is the product.** Every fetched document version is preserved forever with a timestamp. Nothing is ever overwritten or discarded. The versioned corpus is the long-term asset; treat storage of raw snapshots as sacred and design the repo so history cannot be accidentally lost.
2. **Public data only.** Only published documents at public URLs. No login-gated content, no user-submitted documents, no confidential inputs anywhere in the system.
3. **Descriptive, never advisory.** All generated text describes and compares what documents say, with citations to the source document and section. No recommendations, no "you should," no risk ratings of providers. A short standing disclaimer appears on every page and in the README: this is an informational comparison of published documents, not legal advice, documents change, and readers must review the current source documents themselves.
4. **Everything traceable.** Every extracted data point stores: source URL, fetch date, document version hash, and the quoted or paraphrased basis for the extraction. If a value cannot be confidently extracted, store it as "not specified" or "unclear" with a note. Never guess.

## v1 provider set

Hyperscalers: AWS, Microsoft Azure, Google Cloud.
GPU-focused providers: CoreWeave, Lambda (lambda.ai), Crusoe, RunPod, Vast.ai.

For each provider, locate the current public URLs for: (a) general service terms or customer agreement, (b) SLA page(s), prioritizing compute and GPU instance SLAs, (c) acceptable use policy, (d) any AI-specific or GPU-specific service terms. Build a source registry file (YAML) mapping provider to document type to URL, designed so adding a provider later means adding registry entries, not code. During the build, show me the registry for review before wiring it in; I may correct or add URLs.

## v1 term schema (the extraction targets)

For each provider, extract the following into structured data. Values should be categorical or short structured text with a citation, not essays.

1. **Availability definition**: how uptime or availability is defined (instance level, region level, cluster or throughput based, API error rate based, other), and the commitment percentage(s).
2. **Credit regime**: credit tiers (threshold to credit percentage mapping), maximum credit, and whether credits are the sole and exclusive remedy.
3. **Claim mechanics**: whether customer must file a claim, the claim window and how it is measured, and required evidence.
4. **SLA exclusions**: notable exclusions (force majeure, customer fault, maintenance, beta services, single AZ deployments, etc.) as a categorical checklist plus notes.
5. **Capacity and reservation terms**: existence and nature of reserved or committed capacity terms in public documents (take or pay language, use it or lose it, cancellation rights), noting where these are "negotiated, not published."
6. **Data use and AI training**: what the terms say about the provider's rights to use customer data, including any language about training models on customer content.
7. **Suspension rights**: grounds on which the provider may suspend service and whether notice is required.
8. **Termination**: termination for convenience rights (either side), notice periods, and effect on data retrieval (post termination data access window).
9. **Unilateral modification**: whether and how the provider may change the terms, and any notice commitment.
10. **Governing law and disputes**: governing law, forum, arbitration yes or no, class action waiver yes or no.

The extraction layer is a Claude API pass over each document using this schema as structured criteria, returning JSON with a value, a confidence level, and a citation (section heading or quoted anchor under 15 words) for every field. I will review and correct extractions at the checkpoint; corrections are stored as human-verified overrides that survive re-extraction.

## Architecture

- Python, same minimal dependency posture as the radar project.
- Modules: source registry loader, fetcher with per-document snapshot store (raw HTML plus extracted text, content hashed, timestamped, append only), differ (detects changed documents between runs), extractor (Claude API structured extraction per schema), dataset builder (assembles the current comparison dataset plus a change log), site publisher.
- Storage: snapshots as files in a versioned directory structure committed to the repo (raw corpus is the asset); structured data as JSON.
- Scheduling: GitHub Actions weekly run that fetches all sources, snapshots anything changed, re-extracts changed documents only, rebuilds the dataset and site, and commits results.
- API key handling: .env locally, GitHub Actions secret for scheduled runs, .gitignore from the first commit, never in code. Before the first push, verify no key strings exist anywhere in the repo.
- This repo starts private and will be made public later; build everything as if it were already public.

## The public site (static, GitHub Pages)

1. **Matrix view**: providers as columns, term dimensions as rows, cell values with hover or tap detail showing the citation and fetch date. Filterable by provider and term dimension.
2. **Provider detail page**: all extracted terms for one provider with citations and links to source documents, plus that provider's change history.
3. **Change feed**: reverse chronological list of detected document changes, each entry showing provider, document, date detected, and a short neutral description of what changed (old and new language excerpts kept short). This page is the heartbeat of the site.
4. **About page**: what the observatory is, methodology (fetch cadence, extraction approach, human verification), the disclaimer, provider and document coverage list, and a link to the GitHub repo.
5. Clean professional design, readable on mobile, no login, no tracking beyond basic anonymous analytics if free and privacy respecting.

## Build order (checkpoint with me after each step)

1. Repo skeleton, source registry drafted with real URLs for all 8 providers, fetcher and snapshot store working against 2 providers end to end. Show me the registry and a snapshot directory listing.
2. Fetch and snapshot all 8 providers. Differ working (prove it by showing a no-change run and a simulated change).
3. Extractor: run the schema extraction on 2 providers, show me the JSON with citations for my review. I will correct; implement the human-verified override layer. Then extract all 8.
4. Dataset builder and the matrix view page from real data. Show me the rendered site locally.
5. Provider detail pages and the change feed. GitHub Actions weekly workflow. README (legal audience first). Verify secrets hygiene. Prepare for eventual public release.

## Success criteria

One command locally, or the weekly scheduled run, produces: a fully archived corpus of all 8 providers' current documents, a structured comparison dataset where every value carries a citation, and a static site with matrix, provider pages, and change feed that an infrastructure attorney would bookmark. Zero confidential inputs, zero advisory language, complete version history.

## Explicitly out of scope for v1 (do not build)

Negotiated terms data of any kind, user accounts or submissions, email subscriptions, provider ratings or scores, the benchmark project, more than 8 providers, and any paid features. These may come later; keep the code structured so providers and features can be added without rework.
