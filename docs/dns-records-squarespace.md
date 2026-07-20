# DNS records to paste into Squarespace — termsobservatory.org

Prepared 2026-07-19. One row per record. Nothing here needs composing.

Squarespace's editor is **Settings → Domains → termsobservatory.org → DNS Settings**.
Host is sometimes labelled "Name"; leave it as `@` for the root of the domain.

---

## READ THIS FIRST: two existing records must be REPLACED, not added to

The domain currently carries a deliberate "this domain sends no mail" posture. Both
records will actively break Google Workspace if they stay:

| currently live | why it breaks Workspace |
|---|---|
| `TXT @  v=spf1 -all` | Declares that **no** server may send mail for this domain. Google's servers would fail SPF on every message you send. |
| `TXT _dmarc  v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s` | Tells receivers to **reject** anything failing that check. Combined with the above, your own outbound mail gets rejected. |

Delete each of those and paste the replacement below. Do not leave both the old and
new versions in place: two SPF records on one host is itself an SPF failure.

**Already done, no action needed:** DNSSEC is enabled (a DS record is published at
the registry). That item from the security checklist is complete.

---

## 1. Mail delivery (MX)

Google's current single-record setup. Add this one record.

| Host | Type | Priority | Value | TTL |
|---|---|---|---|---|
| `@` | MX | `1` | `smtp.google.com` | 3600 |

> If Squarespace's editor rejects a single MX or the admin console asks for the
> older set, use these five instead **and no others**:
> `ASPMX.L.GOOGLE.COM` (1), `ALT1.ASPMX.L.GOOGLE.COM` (5),
> `ALT2.ASPMX.L.GOOGLE.COM` (5), `ALT3.ASPMX.L.GOOGLE.COM` (10),
> `ALT4.ASPMX.L.GOOGLE.COM` (10).

## 2. SPF — replaces `v=spf1 -all`

| Host | Type | Value | TTL |
|---|---|---|---|
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` | 3600 |

`~all` (softfail) rather than `-all` while mail is new: a hard fail during setup
sends legitimate mail to oblivion with no diagnostics. Tighten to `-all` once the
DMARC reports in item 5 come back clean.

## 3. DMARC — reports go to a processor, not your inbox

DMARC aggregate reports are XML, sent daily by every major receiver. Rather than
have that land in `contact@`, a free processor ingests them and sends one readable
digest instead. The `rua` address below is issued by the processor at signup.

**Step 1 — get the address (two minutes, no card).**

Use **Postmark's DMARC monitoring**: <https://dmarc.postmarkapp.com>. Enter the
domain and the address that should receive the weekly digest. It returns an `rua`
address of the form `re+xxxxxxxxx@dmarc.postmarkapp.com`.

(Alternative if you prefer: dmarcian's free tier, <https://dmarcian.com>. Same
idea, same record shape. Either is fine; Postmark needs no account.)

**Step 2 — paste the record**, substituting the address from step 1:

| Host | Type | Value | TTL |
|---|---|---|---|
| `_dmarc` | TXT | `v=DMARC1; p=quarantine; rua=mailto:re+xxxxxxxxx@dmarc.postmarkapp.com; fo=1; adkim=s; aspf=s` | 3600 |

Starting at `quarantine` rather than `reject` is deliberate: it is reversible while
the setup is new. FOLLOWUPS carries a two-week check to move to `reject` once the
digests show legitimate mail passing consistently.

> **If you would rather receive nothing at all**, this is also a valid record and
> publishes the same enforceable policy:
> `v=DMARC1; p=quarantine; fo=1; adkim=s; aspf=s`
> The cost is visibility: no reports means no evidence for the `p=reject` decision
> and no warning if someone starts spoofing the domain.

## 4. Google-issued values — PLACEHOLDERS, only Google can generate these

Google gives you these during signup and in the admin console. Paste them the same
way; the host and type are already correct.

| Host | Type | Value | TTL | Where it comes from |
|---|---|---|---|---|
| `@` | TXT | `google-site-verification=________________` | 3600 | Shown during Workspace signup, domain verification step |
| `google._domainkey` | TXT | `v=DKIM1; k=rsa; p=________________` | 3600 | Admin console → Apps → Google Workspace → Gmail → **Authenticate email**. Generate a 2048-bit key, then click **Start authentication** after the record resolves. |

DKIM is not on by default. Generating the key is not enough — the "Start
authentication" step is the one people miss.

## 5. CAA — restricts who may issue certificates for the domain

| Host | Type | Value | TTL |
|---|---|---|---|
| `@` | CAA | `0 issue "letsencrypt.org"` | 3600 |
| `@` | CAA | `0 iodef "mailto:contact@termsobservatory.org"` | 3600 |

GitHub Pages provisions its certificates through Let's Encrypt, so that is the only
issuer authorised. The `iodef` line asks non-authorised CAs to report attempts.

> **Caution.** If GitHub ever changes certificate provider, a CAA record naming only
> Let's Encrypt will block renewal and the site will eventually serve an expired
> certificate. That failure is silent until it isn't. If the site's certificate ever
> fails to renew, delete the CAA records first and investigate second.

---

## Order of operations

1. Delete the two old records (SPF, DMARC). Add the new SPF and DMARC.
2. Add the MX record.
3. Add the Google verification TXT when signup shows it.
4. Complete signup, then generate and add the DKIM record, then click Start
   authentication.
5. Add the two CAA records last, so a mistake there cannot complicate mail setup.
6. Tell me when they are in and I will verify all of it externally (item B9).

DNS propagation is usually minutes on Squarespace but the TTL allows an hour.
