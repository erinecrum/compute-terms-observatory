# Security

## Reporting

Report security issues to **contact@termsobservatory.org**.

Please include enough detail to reproduce. Enquiries about published document text
rather than the software reach the same address; see "Document versions" below.

There is no bug bounty. This is a single-maintainer research project.

## What this project is, in security terms

A static site on GitHub Pages built from a Python pipeline that fetches public
documents. It has **no server, no database, no user accounts, no forms, and no
user-submitted input**. Most web-application risk does not apply. The assets worth
protecting are:

1. **CI secrets** — an Anthropic API key (spendable) and a token with write access
   to the private corpus repository.
2. **Content integrity** — the site publishes readings of providers' legal terms
   under the maintainer's name. Silent tampering is the highest-consequence risk
   here, above availability.
3. **Visitor safety** — the site renders text fetched from third parties.

## What is in place

**Content Security Policy.** Delivered by meta tag, hash-based: each page allows
only the exact inline script and style blocks that build emitted, with
`default-src 'none'` and `connect-src 'none'`. No `unsafe-inline`. Verified by
attack rather than by reading the policy: an injected inline `<script>` does not
execute, and external scripts, `fetch()` to another origin, and image beacons are
all blocked. This makes the site's zero-third-party-request property a rule the
browser enforces rather than a convention.

**Untrusted input handling.** Provider documents are third-party text rendered into
HTML. All values pass an escaping boundary; verified by parsing rendered output
after injecting hostile payloads, with no injected elements and no event handlers
surviving. URL schemes are allowlisted to http/https/mailto, because escaping makes
a `javascript:` URL safe as text but not as an `href`.

**Supply chain.** Python dependencies are pinned to exact versions, and GitHub
Actions are pinned to commit SHAs rather than mutable tags. Both matter because CI
runs with the secrets above; a compromised release or a repointed tag would execute
with them. Dependabot is enabled and raises security updates as pull requests.
Updates are reviewed and merged deliberately, never auto-merged.

**Repository.** Secret scanning and push protection are enabled, so a key committed
by mistake is blocked at push rather than discovered later.

**Transport.** HTTPS is enforced by GitHub Pages, with certificates provisioned
through Let's Encrypt. A CAA record restricts certificate issuance to that issuer.

**Domain.** DNSSEC is enabled. SPF, DKIM and DMARC are published for the domain's
Google Workspace mail; see `docs/dns-records-squarespace.md` for the records and
their rationale.

## What GitHub Pages cannot provide

Documented so the limits are known rather than assumed:

- **No custom HTTP response headers.** Pages serves a fixed set. Anything normally
  delivered by header must be expressed in a meta tag or not at all. In practice:
  `Content-Security-Policy` works by meta, but `Strict-Transport-Security`,
  `X-Frame-Options` and `Permissions-Policy` cannot be set. `frame-ancestors` is
  ignored in meta form, so **clickjacking cannot be blocked**. The site has no
  authenticated state or state-changing actions, so there is nothing to hijack, but
  the gap is real rather than solved.
- **`X-Content-Type-Options: nosniff` and `Referrer-Policy` cannot be set by
  header.** `Referrer-Policy` is expressible as a meta tag and is set;
  `X-Content-Type-Options` has no meta equivalent and is not set.
- **No rate limiting, no WAF, no request logging** available to the maintainer.
  Availability and abuse handling are entirely GitHub's.
- **No server-side anything**, which is also why the attack surface is small.

## Mail

The domain runs Google Workspace. **contact@termsobservatory.org** is the single
public address: security reports, document-versions enquiries, and provider
correspondence all arrive there. One address is easier to monitor reliably than
three, and an unmonitored alias is worse than no alias.

SPF authorises Google's servers, DKIM is published, and DMARC is enforced. DMARC
aggregate reports are routed to a monitoring service rather than to the public
address, so the mailbox stays human-readable. The policy starts at `quarantine`
while the setup is new and moves to `reject` once the reports are clean.

## Credentials and rotation

CI uses two secrets, both repository-scoped:

- `ANTHROPIC_API_KEY` — extraction. Rotate if a workflow log is ever made public.
- `DATA_REPO_TOKEN` — read/write access to the private corpus repository.

`DATA_REPO_TOKEN` is a fine-grained personal access token, scoped to the single
private corpus repository with contents read/write and nothing else, and carrying an
expiry. It is deliberately not a classic token: a classic PAT's `repo` scope reaches
every repository the account owns, so a leak from CI would expose far more than the
corpus. Rotate every 90 days; FOLLOWUPS carries the reminder. Rotating means issuing a new token, updating the repository
secret, and confirming a pipeline run succeeds before revoking the old one.

## Document versions

Captured document versions are published so readers can independently verify the
Observatory's change reports. The Observatory reproduces these publicly posted
terms for documentation and verification purposes. Providers who wish to discuss
the presentation of their documents may contact contact@termsobservatory.org.
