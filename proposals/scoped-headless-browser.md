# Proposal: extend the headless-browser tier to the JS-rendered trust centres

**Status: proposal only. Nothing implemented. To be decided alongside the Phase A report.**
Raised 2026-07-19, following the source health audit.

## Correction to the premise

This is not a proposal to *add* Playwright. **Playwright and Chromium are already
installed and in use** in the twice-daily workflow, and nine documents are already
registered `fetch_method: browser`:

```
claude/deprecation      openai/service_terms   openai/business_terms
openai/aup              grok/service_terms     grok/aup
grok/dpa                grok/privacy_policy    deepseek/service_terms
```

The browser tier is also already allowlisted, in the only way that matters: it is
opt-in per document via the registry, never a global fallback. So the real question
is narrower than "should we adopt headless browsing" — it is **whether to add six
more documents to a capability that already exists and already runs every twelve
hours.**

## The six candidates

All six currently fail identically: HTTP 200, then zero characters of text, because
the content is rendered client-side. The fetcher correctly refuses to snapshot an
empty document rather than record a false "provider deleted their terms".

| document | host | pattern |
|---|---|---|
| claude / subprocessor_list | trust.anthropic.com | SafeBase-style trust centre |
| crusoe / privacy_policy | crusoe.ai | JS-rendered |
| crusoe / subprocessor_list | crusoe.ai | JS-rendered |
| gemini / transparency_report | transparencyreport.google.com | JS-rendered |
| llama / ai_documentation | llama.com | JS-rendered |
| mistral-platform / subprocessor_list | trust.mistral.ai | SafeBase-style trust centre |

Under the current decisions these are marked **Not retrievable (JavaScript-rendered)**,
which is honest but is a coverage gap in exactly the dimensions the data-protection
expansion is meant to cover: sub-processor transparency and government access.

## Cost

Measured from the 2026-07-19 run, not estimated:

| step | duration |
|---|---|
| Install Playwright + Chromium | **26s** |
| Full pipeline (fetch, extract, build, site) | 12m 27s |
| Total job | ~13m 13s |

The install cost is **already being paid every run** whether or not these six are
added. The marginal cost of six more browser-tier documents is the page-load time
alone: the browser tier uses a 45-second `networkidle` timeout, so the realistic
marginal cost is **roughly 30 to 90 seconds per run**, worst case about 4m 30s if
every one of the six times out. Against a 13-minute job on free-tier GitHub Actions
minutes for a public repository, this is not a meaningful cost.

The honest risk is not compute, it is **timeout noise**: the browser tier already
produces most of the audit's failure signals (grok and openai timeouts). Adding six
JS-heavy pages will add more, and a fetch step that routinely half-fails erodes the
signal value of the failure log.

## What I would actually propose

1. **Add the six to the registry as `fetch_method: browser`.** No code change is
   required; this is a registry edit, which is the whole point of the existing
   design.
2. **Raise the browser timeout for trust-centre hosts specifically**, or accept
   failures on them. SafeBase-style pages load a shell fast and hydrate slowly, so a
   `networkidle` wait is the wrong signal for them; waiting on a content selector
   would be better but is per-host configuration, which the registry does not model
   today. This is the only part that needs real code.
3. **Keep the allowlist explicit.** The browser tier must stay opt-in per document.
   A global "retry everything in a browser" fallback would quietly turn every
   transient failure into a 45-second stall across 150 documents.
4. **Do not bypass anything.** None of these six block automated access; they are
   simply client-rendered. The moment a candidate turns out to be CAPTCHA-gated or
   login-walled it leaves this proposal and becomes **Access restricted by
   provider**, per the existing rule. That boundary is not negotiable and this
   proposal does not touch it.

## Recommendation

Approve items 1, 3 and 4 now: they are a registry edit plus a restatement of
existing policy, and they close six gaps in the data-protection dimensions at
negligible cost.

Hold item 2 until the corpus expansion scoping is done, because per-host wait
configuration should be designed once, against the full set of hosts the expansion
adds, rather than retrofitted for two trust centres now and redesigned later.

## Open questions

1. Should the six be added before or after the corpus expansion, given the expansion
   will likely add more trust-centre hosts with the same pattern?
2. Is per-host browser configuration (wait strategy, selector, timeout) worth adding
   to the registry schema, or should trust centres simply be accepted as
   low-yield sources?
3. If a trust centre requires an email address or account to view the sub-processor
   list, that is a login wall: confirm it becomes **Access restricted by provider**
   and is not pursued further.
