# Follow-ups (not yet actioned)

Deferred items to revisit deliberately, not in passing.

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
