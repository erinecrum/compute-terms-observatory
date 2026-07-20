# Follow-ups (not yet actioned)

Deferred items to revisit deliberately, not in passing.

## Wrong-page captures are a class, not an incident

A capture can be a real page, cleanly fetched, HTTP 200, from the correct domain and
the correct org namespace, of adequate length -- and be the wrong page.

The instance: Qwen's model card was captured from the Hugging Face org LANDING page,
2,889 characters of activity feed, after the registry URL moved and before the next
fetch. Every provenance and content-floor check passed, because every one of them was
satisfied. Nothing was broken; the wrong document was simply sitting where the right
one should be.

Why the existing controls cannot own this class:

- **Content floors** measure size. A wrong page is often a perfectly normal size.
- **Provenance and domain checks** verify where a capture came from. This one came
  from exactly the right place.
- **The generation check** compares a document's text to the tracked generation, but
  only fires where the text names SOME generation. An activity feed names many.
- **The fingerprint check** (added 2026-07-20) catches the common shape by requiring
  the tracked generation to appear. Note it initially MISSED the Qwen case: the org
  feed is wall-to-wall "Qwen", so a family-name match succeeded. It only works
  because it demands the specific checkpoint. Anything looser reproduces the defect.

So the fingerprint narrows the class; it does not own it. **The audit pass owns this
class**, because reading the document and asking what it is, is the only check that
does not depend on guessing the right string in advance.

This is the reason the audit pass cannot be retired once the registry stabilises. A
stable registry is exactly the condition under which this defect is invisible: no
edits, no new sources, nothing to review, and a capture quietly pointing at the wrong
page for months. Do not let a quiet quarter become an argument for switching it off.

Raised 2026-07-20.

## Quarterly full-registry governs review

**Next due: 2026-10-20**, then quarterly.

Read every fetchable document's `governs` line against the document itself and the
entry it sits on, in one pass, deliberately. Same shape as the sweep on 2026-07-19
that found the Meta consumer privacy policy filed against the Llama weights.

The reason this has a cadence: every governing-document violation found so far was
found by accident. Llama's came from a deliberate sweep, but Kimi's, GLM's and
MiniMax's each surfaced only because an unrelated check suppressed their values and
someone asked why an entry looked empty. Violations that produce confident,
well-sourced, WRONG values -- the more likely shape, since a wrong document usually
has plenty to say -- generate no such signal at all.

The layered controls added on 2026-07-20 (doc-type lint, scope-clause check,
monthly adversarial audit) narrow the gap but cannot close it: whether a given
instrument governs a given artifact is a judgment. This review is where that
judgment gets spent on purpose rather than on prompting.

Working method:

1. `python scripts/governance_audit.py` for a fresh triage list.
2. Work the contested list, then read the clean list's `basis` lines too: the audit
   agreeing is not the same as the basis being right.
3. Check `data/scope_flags.json` and the generation report in the same pass.
4. Record dispositions in the registry notes, including the ones you decline to
   change and why.

Raised 2026-07-20.

## mistral-open has no governing document

The legal index page (legal.mistral.ai/terms) was removed on 2026-07-20: it is a table
of contents, and an index governs nothing. The entry now renders 22 dimensions as
not-retrievable, which is its true state, rather than borrowing a document.

**Decision needed: which family does this entry track?** Mistral publishes across both
Apache-2.0 and its own research licence, so the answer determines the licence.

Findings from the 2026-07-20 probe:

- Mistral ships **no LICENSE file** in its Hugging Face repos. Every candidate probed
  returned 404 for `/raw/main/LICENSE`. The licence is declared in the model card
  front matter (`license: apache-2.0`) and the repo tag.
- `mistralai/Mistral-Large-3` is the current flagship and declares Apache-2.0; its
  card states "Apache 2.0 License: Open-source license allowing usage and modification
  for both commercial and non-commercial purposes". Mistral-Small-3.2 and
  Magistral-Small-2509 also declare Apache-2.0.
- The Mistral Research Licence exists at mistral.ai/static/licenses/MRL-0.1.md and
  applies to other families.

This creates a wrinkle worth deciding deliberately: with no LICENSE file, a
`model_license` document has no URL to point at that is not also the model card. Either
the licence is recorded as declared-within-the-model-card, or the entry carries only an
`ai_documentation` document and the licence dimension is sourced from it.

Raised 2026-07-20.

## Qwen tracked generation lags the provider's own documentation

The registry now tracks **Qwen3-235B-A22B** (Apache-2.0), moved from Qwen2.5-72B on
2026-07-19. Qwen's own `ai_documentation` names **Qwen3.5 and Qwen3.6**, but no
license resolves at those Hugging Face paths yet (401), so the flagship with a
resolvable license is as far as the tracked generation can move today.

Recheck `huggingface.co/Qwen/Qwen3.5-*` and `Qwen3.6-*` at the next run and move the
tracked generation again when a newer flagship license resolves. Each move is an
Observatory curation update, not a provider relicensing.

Raised 2026-07-19.

## Per-host fetch tuning candidates (expansion scoping)

Sources failing for host-specific reasons rather than policy ones. Each needs a
decision during the corpus expansion, not a blanket retry:

- **grok/service_terms, grok/dpa** - browser-tier timeouts at the 45s `networkidle`
  wait against x.ai. Candidates for per-host wait tuning (a content selector rather
  than network idle). grok/aup and grok/privacy_policy currently succeed, so the
  host is reachable and the wait strategy is the variable.
- **coreweave/privacy_policy** - the provider's own redirect is broken:
  `coreweave.com/privacy-policy/` 301s to `http://www.coreweave.com:8080/privacy-policy`,
  plain HTTP on a port that does not answer. No URL substitution fixes it; needs a
  different source or a note to CoreWeave.
- **deepseek/service_terms** - CAPTCHA-gated, no archive available. Access
  restricted by provider; not pursued.
- **gemini/transparency_report, crusoe/privacy_policy** - captured, but below the
  content floor (234 and 2231 chars): landing pages rather than documents. Deeper
  URLs to be hunted during expansion scoping.

Raised 2026-07-19.

## Substack sequencing

License-divergence article is post one; OpenAI Business Terms -> Services Agreement
transition is a candidate later post, framed as document restructure analysis,
arbitration retained.

Raised 2026-07-19.

## DMARC: tighten the policy in two steps

Verified live 2026-07-19: MX, SPF, DKIM and DMARC all pass. Policy currently sits at
`p=none`, which is monitoring only. Aggregate reports go to a Postmark digest rather
than the mailbox.

**Step 1, from 2026-08-02.** If the digests show legitimate mail passing SPF and
DKIM consistently, move to quarantine and tighten SPF alignment:

    v=DMARC1; p=quarantine; pct=100; rua=mailto:re+c1mghgxwsqv@dmarc.postmarkapp.com; sp=quarantine; aspf=s;

**Step 2, roughly two weeks after that**, if still clean, move to reject and tighten
SPF from `~all` to `-all` in the same session:

    v=DMARC1; p=reject; pct=100; rua=mailto:re+c1mghgxwsqv@dmarc.postmarkapp.com; sp=reject; aspf=s;

Do not skip step 1, and do not tighten while any report still shows failures: that
rejects your own mail. Paste through a plain-text editor; the first attempt at this
record picked up a stray tab that silently invalidated it.

Note: termsobservatory.com is separately configured as a non-sending domain
(`v=spf1 -all`, DMARC `p=reject`, no MX). That is correct and needs no change.

## Rotate DATA_REPO_TOKEN every 90 days

Set 2026-07-19, next rotation due **2026-10-17**. Issue the replacement, update the
repository secret, confirm a pipeline run succeeds, then revoke the old token. See
SECURITY.md for the required scope (fine-grained, single private repo, contents
read/write only).
