# Working instructions for this repo

## Who you are working with
I am a practicing technology transactions attorney, not a professional developer. I direct the build and make all product and legal judgment calls. Explain technical decisions in one or two plain English sentences when you make them. Do not assume I know framework conventions.

## How to work
- Follow the build order in compute-terms-observatory-spec.md exactly. Stop at each numbered checkpoint and wait for my review before continuing. Do not start the next step early even if it seems obvious.
- Ask before adding any dependency, service, or abstraction not in the spec. Default answer is no. Minimal dependencies, boring choices, readable code over clever code.
- If the spec is ambiguous or two requirements conflict, ask me rather than picking silently.
- When you show me something for review, show the actual artifact (file contents, directory listing, rendered output), not a summary of it.
- Small commits with plain English messages describing what changed and why.

## Hard rules (never violate, never work around)
- Never delete, overwrite, or rewrite anything in the snapshot store. Snapshots are append only. If a fetch fails or produces garbage, record the failure; do not touch prior snapshots. No git history rewrites on snapshot directories.
- Public data only. Never add code paths that accept user uploads, credentials for gated content, or any non public input.
- All generated text on the site must be descriptive, never advisory. No recommendations, no risk scores, no "should." If Claude API output comes back advisory in tone, regenerate or flag it to me.
- Every extracted value must carry source URL, fetch date, content hash, and a citation. If extraction is uncertain, the value is "unclear" with a note. Never fill a field by inference.
- Quoted excerpts from provider documents stay under 15 words everywhere: extractions, change feed entries, site copy.
- Human verified overrides always win over fresh extractions. Never let a re-extraction clobber one.
- API keys: .env locally, GitHub secret in Actions, .gitignore before first commit. Before any push, grep the repo for key patterns and confirm clean.
- Respect robots.txt and fetch politely: identify with a clear user agent, one request at a time, back off on errors. We are archivists, not scrapers evading anyone.

## Style for anything user facing
- No em dashes in any site copy, README text, or change feed descriptions.
- Plain professional English written for attorneys, not developers.
- The disclaimer from the spec appears on every page and in the README.
