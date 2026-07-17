"""Static site generator. Renders the comparison dataset to plain HTML files in
site/ — no framework, no external assets, no tracking, so it hosts on GitHub Pages
and also opens straight from disk. CSS/JS are inlined via a shared shell.

Step 4 renders the matrix view and the About page. Provider detail pages and the
change feed are added in the next step; the shell and nav already anticipate them.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import List

SITE_DIR = Path("site")
EXPORT_XLSX = "compute-terms-observatory.xlsx"

_CONF_LABEL = {"high": "high", "medium": "medium", "low": "low", "verified": "verified"}

# A small "comparison columns" mark, used as the header emblem and the favicon.
_EMBLEM = (
    '<svg class="emblem" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">'
    '<rect width="32" height="32" rx="7" fill="currentColor"/>'
    '<rect x="7" y="9" width="4" height="14" rx="1.5" fill="#fff"/>'
    '<rect x="14" y="9" width="4" height="14" rx="1.5" fill="#fff"/>'
    '<rect x="21" y="9" width="4" height="14" rx="1.5" fill="#fff"/></svg>'
)
_FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='7' fill='%231c3f63'/%3E"
    "%3Crect x='7' y='9' width='4' height='14' rx='1.5' fill='%23fff'/%3E"
    "%3Crect x='14' y='9' width='4' height='14' rx='1.5' fill='%23fff'/%3E"
    "%3Crect x='21' y='9' width='4' height='14' rx='1.5' fill='%23fff'/%3E%3C/svg%3E"
)


def esc(s) -> str:
    # House style (CLAUDE.md): no em/en dashes in any site copy. Sanitize at the
    # render boundary so dashes from model output, notes, or citations never leak
    # into the page.
    text = str(s if s is not None else "").replace("—", "-").replace("–", "-")
    return html.escape(text)


def _shell(title: str, body: str, active: str, subtitle: str = "") -> str:
    nav_items = [("index.html", "Matrix"), ("changes.html", "Change feed"), ("about.html", "About")]
    nav = "".join(
        f'<a href="{href}" class="{"active" if key==active else ""}">{esc(label)}</a>'
        for href, label in [(h, l) for h, l in nav_items]
        for key in [href.split(".")[0]]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="icon" href="{_FAVICON}">
<style>{_CSS}</style>
</head>
<body>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="index.html">{_EMBLEM}<span class="wordmark">Compute Contract Terms<br><span class="wordmark-2">Observatory</span></span></a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
<div class="disclaimer"><div class="wrap">
  <span class="disc-icon" aria-hidden="true">i</span>
  <span><strong>AI-generated summaries, not legal advice.</strong>
  Every value here is an AI's reading of a provider's public terms, not the terms themselves. It can be
  wrong, incomplete, or out of date. We link each value to its source document, so verify anything
  yourself before you rely on it.</span></div></div>
<main class="wrap">
  <h1>{esc(title)}</h1>
  {f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ''}
  {body}
</main>
<footer class="site-foot"><div class="wrap">
  Public documents only · Descriptive, never advisory ·
  <a href="https://github.com/erinecrum/compute-terms-observatory">Source & methodology</a>
</div></footer>
<script>{_JS}</script>
</body>
</html>"""


def _conf_dot(confidence: str, verified: bool) -> str:
    if verified:
        return '<span class="dot verified" title="human-verified"></span>'
    c = confidence if confidence in ("high", "medium", "low") else "low"
    return f'<span class="dot {c}" title="model confidence: {c}"></span>'


def _cell(provider: str, dim_key: str, field: dict) -> str:
    value = field.get("value", "")
    citation = field.get("citation", "")
    source = field.get("source")
    verified = field.get("human_verified", False)
    conf = field.get("confidence", "low")
    prog = field.get("commitment_program")

    src_line = ""
    if source:
        src_line = (
            f'<div class="src">Source: <a href="{esc(source["url"])}" target="_blank" rel="noopener">'
            f'{esc(source["name"])}</a> · fetched {esc(source.get("fetched_at","")[:10])}</div>'
        )
    cite_line = f'<div class="cite">“{esc(citation)}”</div>' if citation else ""
    verified_badge = '<span class="badge verified">✓ human-verified</span>' if verified else ""
    prog_line = ""
    if prog:
        prog_line = (
            f'<div class="prog"><strong>{esc(prog["program"])}:</strong> {esc(prog["value"])} '
            f'(<a href="{esc(prog["citation_url"])}" target="_blank" rel="noopener">program</a>)</div>'
        )

    short = value if len(value) <= 160 else value[:157] + "…"
    return f"""<td class="cell" data-provider="{esc(provider)}" data-dim="{esc(dim_key)}">
  <div class="cell-head">{_conf_dot(conf, verified)} <button class="toggle" aria-expanded="false">{esc(short)}</button></div>
  <div class="detail" hidden>
    <div class="full">{esc(value)}</div>
    {cite_line}{prog_line}{src_line}
    <div class="meta">{verified_badge}<span class="conf-label">{esc(_CONF_LABEL.get(conf, conf))}</span></div>
  </div>
</td>"""


def render_matrix(dataset: dict) -> str:
    dims = dataset["dimensions"]
    providers = dataset["providers"]
    matrix = dataset["matrix"]

    # Filter controls
    prov_checks = "".join(
        f'<label><input type="checkbox" class="f-prov" value="{esc(p["provider"])}" checked> {esc(p["provider_name"])}</label>'
        for p in providers
    )
    dim_checks = "".join(
        f'<label><input type="checkbox" class="f-dim" value="{esc(d["key"])}" checked> {esc(d["label"])}</label>'
        for d in dims
    )

    head_cells = "".join(
        f'<th class="prov-col" data-provider="{esc(p["provider"])}">'
        f'<a href="provider-{esc(p["provider"])}.html">{esc(p["provider_name"])}</a>'
        f'<span class="col-updated">updated {esc((p.get("last_updated") or "")[:10])}</span></th>'
        for p in providers
    )
    rows = []
    ncols = len(providers) + 1
    current_group = None
    for d in dims:
        g = d.get("group", "")
        if g and g != current_group:
            current_group = g
            rows.append(
                f'<tr class="grouprow" data-group="{esc(g)}">'
                f'<th class="groupcell" colspan="{ncols}">{esc(g)}</th></tr>'
            )
        cells = []
        for p in providers:
            field = matrix.get(p["provider"], {}).get(d["key"])
            if field is None:
                cells.append(f'<td class="cell empty" data-provider="{esc(p["provider"])}" data-dim="{esc(d["key"])}">n/a</td>')
            else:
                cells.append(_cell(p["provider"], d["key"], field))
        rows.append(
            f'<tr data-dim="{esc(d["key"])}" data-group="{esc(g)}">'
            f'<th class="dim-col" title="{esc(d["guidance"])}">{esc(d["label"])}</th>{"".join(cells)}</tr>'
        )

    legend = (
        '<div class="legend"><span class="legend-lbl">Confidence</span>'
        '<span class="lg"><span class="dot high"></span>high</span>'
        '<span class="lg"><span class="dot medium"></span>medium</span>'
        '<span class="lg"><span class="dot low"></span>low / not specified</span>'
        '<span class="lg"><span class="dot verified"></span>human-verified</span></div>'
    )

    gen = dataset.get("generated_at", "")[:16].replace("T", " ")
    current = esc((dataset.get("data_current_as_of", "") or "")[:10])
    return f"""
<div class="actions">
  <a class="btn" href="{EXPORT_XLSX}" download>Download Excel (.xlsx)</a>
  <button class="btn ghost" type="button" onclick="window.print()">Print / Save as PDF</button>
  <span class="updated">Data current as of {current}</span>
</div>
<div class="filters">
  <details open><summary>Filter providers</summary><div class="checks">{prov_checks}</div></details>
  <details><summary>Filter dimensions</summary><div class="checks">{dim_checks}</div></details>
</div>
<div class="toolbar">{legend}<span class="hint">Tip: click any cell for the full value, citation, source link, and fetch date.</span></div>
<div class="table-scroll">
  <table class="matrix">
    <thead><tr><th class="corner">Term dimension</th>{head_cells}</tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</div>
<p class="genline">Generated {esc(gen)} UTC · {len(providers)} providers · {len(dims)} term dimensions.</p>
"""


def render_about(dataset: dict) -> str:
    providers = dataset["providers"]
    dims = dataset["dimensions"]
    prov_list = "".join(
        f"<li><strong>{esc(p['provider_name'])}</strong>: "
        + ", ".join(esc(doc["name"]) for doc in p["documents"])
        + "</li>"
        for p in providers
    )
    dim_list = "".join(f"<li><strong>{esc(d['label'])}</strong>: {esc(d['guidance'])}</li>" for d in dims)
    return f"""
<h2>What this is</h2>
<p>An AI reads each provider's <em>public</em> terms of service, SLAs, acceptable use policies,
and AI-specific terms against a fixed 10-term schema, and records what it finds with a citation
and a source link for every value. These are the AI's summaries of what the documents say, not the
documents themselves and not legal advice. They can be wrong, incomplete, or out of date, which is
why every value links to its source: so you can verify it yourself before relying on it. It does not
advise, recommend, or rate.</p>

<h2>Methodology</h2>
<ul>
<li><strong>Archival.</strong> Every fetched document version is preserved with a timestamp and content hash; nothing is overwritten.</li>
<li><strong>Extraction.</strong> A structured pass with Claude (Opus) reads each provider's documents against a fixed 10-term schema, returning a value, a confidence level, and a citation for every field. Values it cannot support are recorded as “not specified” or “unclear”, never guessed.</li>
<li><strong>Human verification.</strong> Extractions can be corrected; corrected fields are marked human-verified and survive re-extraction.</li>
<li><strong>Provenance.</strong> Every value links to its source document, with the fetch date and version hash behind it.</li>
</ul>

<h2>Coverage</h2>
<h3>Providers &amp; documents</h3>
<ul class="coverage">{prov_list}</ul>
<h3>Term dimensions</h3>
<ul class="coverage">{dim_list}</ul>

<h2>Disclaimer</h2>
<p>{esc(dataset.get("disclaimer",""))} Nothing here creates an attorney-client relationship.</p>
"""


def render_provider(dataset: dict, pmeta: dict) -> str:
    provider = pmeta["provider"]
    fields = dataset["matrix"].get(provider, {})
    dims = dataset["dimensions"]

    # Documents used, with provenance.
    docs = "".join(
        f'<li><a href="{esc(d["url"])}" target="_blank" rel="noopener">{esc(d["name"])}</a> '
        f'<span class="tag">{esc(d["doc_type"])}</span> · fetched {esc(d["fetched_at"][:10])} · '
        f'<code>{esc(d["text_sha256"][:12])}</code>'
        f'{" · <em>truncated for length</em>" if d.get("truncated") else ""}</li>'
        for d in pmeta.get("documents", [])
    )

    rows = []
    for dim in dims:
        f = fields.get(dim["key"])
        if not f:
            continue
        verified = f.get("human_verified", False)
        conf = f.get("confidence", "low")
        source = f.get("source")
        prog = f.get("commitment_program")
        cite = f'<div class="cite">“{esc(f.get("citation",""))}”</div>' if f.get("citation") else ""
        src = ""
        if source:
            src = (f'<div class="src">Source: <a href="{esc(source["url"])}" target="_blank" rel="noopener">'
                   f'{esc(source["name"])}</a> · fetched {esc(source.get("fetched_at","")[:10])} · '
                   f'<code>{esc(source.get("text_sha256","")[:12])}</code></div>')
        progline = ""
        if prog:
            progline = (f'<div class="prog"><strong>{esc(prog["program"])}:</strong> {esc(prog["value"])} '
                        f'(<a href="{esc(prog["citation_url"])}" target="_blank" rel="noopener">program page</a>). {esc(prog.get("note",""))}</div>')
        badge = '<span class="badge verified">✓ human-verified</span>' if verified else ''
        note = f'<div class="ovnote">{esc(f.get("override_note",""))}</div>' if f.get("override_note") else ''
        rows.append(f"""
<section class="pdim">
  <h3>{_conf_dot(conf, verified)} {esc(dim["label"])} {badge}</h3>
  <p class="pval">{esc(f.get("value",""))}</p>
  {cite}{progline}{note}{src}
</section>""")

    # This provider's change history.
    changes = [c for c in dataset.get("change_log", []) if c["provider"] == provider]
    if changes:
        chitems = "".join(_change_item(c) for c in changes)
        change_html = f'<div class="changes">{chitems}</div>'
    else:
        change_html = '<p class="empty">No changes detected yet. The current snapshots are the baseline.</p>'

    return f"""
<p><a href="index.html">← Back to matrix</a></p>
<h2>Documents archived</h2>
<ul class="coverage">{docs}</ul>
<h2>Extracted terms</h2>
{"".join(rows)}
<h2>Change history</h2>
{change_html}
<p class="genline">Extracted {esc(pmeta.get("extracted_at","")[:16].replace("T"," "))} UTC with {esc(pmeta.get("model",""))}.</p>
"""


def _change_item(c: dict) -> str:
    blocks = "".join(
        f'<div class="cblock"><div class="old">− {esc(b["old"])}</div><div class="new">+ {esc(b["new"])}</div></div>'
        for b in c.get("blocks", [])
    )
    if c.get("source_changed"):
        meta = f'<div class="cmeta">{esc(c.get("note",""))} <a href="{esc(c["url"])}" target="_blank" rel="noopener">source</a></div>'
    else:
        meta = (
            f'<div class="cmeta">+{c.get("added_lines",0)} / {c.get("removed_lines",0)} lines removed · '
            f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">source</a></div>'
        )
    ai = ""
    dims = c.get("dimensions", [])
    chips = ""
    if dims:
        chips = '<div class="chips">' + "".join(
            f'<span class="chip">{esc(d["label"])}</span>' for d in dims
        ) + "</div>"
    if c.get("ai_explanation"):
        ai = (
            f'<div class="ai-note"><span class="ai-label">AI summary of this change</span>'
            f'<p>{esc(c["ai_explanation"])}</p>{chips}'
            f'<span class="ai-verify">This is an AI-generated description. Verify it against the '
            f'source document before relying on it.</span></div>'
        )
    dim_keys = " ".join(d["key"] for d in dims)
    return f"""
<article class="change" data-provider="{esc(c["provider"])}" data-pname="{esc(c["provider_name"])}"
  data-date="{esc(c["detected_at"][:10])}" data-dims="{esc(dim_keys)}">
  <div class="chead"><strong>{esc(c["provider_name"])}</strong>: {esc(c["document"])}
    <span class="tag">{esc(c["doc_type"])}</span>
    <span class="cdate">{esc(c["detected_at"][:10])}</span></div>
  {meta}
  {ai}
  {blocks}
</article>"""


def render_changes(dataset: dict) -> str:
    log = dataset.get("change_log", [])
    if not log:
        return """
<p class="empty">No document changes detected yet. This feed is the observatory's heartbeat.
Once a provider edits a tracked document, the change (with short before/after excerpts) appears
here in reverse-chronological order. The current run establishes the baseline.</p>"""

    # Build filter options from the changes that actually exist.
    providers = {}
    for c in log:
        providers.setdefault(c["provider"], c["provider_name"])
    provisions = {}
    for c in log:
        for d in c.get("dimensions", []):
            provisions.setdefault(d["key"], d["label"])

    dates = sorted(c["detected_at"][:10] for c in log)
    prov_checks = "".join(
        f'<label><input type="checkbox" class="cf-prov" value="{esc(k)}" checked> {esc(v)}</label>'
        for k, v in providers.items()
    )
    prv_checks = "".join(
        f'<label><input type="checkbox" class="cf-dim" value="{esc(k)}" checked> {esc(v)}</label>'
        for k, v in sorted(provisions.items(), key=lambda kv: kv[1])
    )
    controls = f"""
<div class="cf-controls">
  <div class="cf-row">
    <label>Sort
      <select id="cf-sort">
        <option value="date-desc">Newest first</option>
        <option value="date-asc">Oldest first</option>
        <option value="prov">Provider A to Z</option>
      </select>
    </label>
    <label>From <input type="date" id="cf-from" min="{esc(dates[0])}" max="{esc(dates[-1])}"></label>
    <label>To <input type="date" id="cf-to" min="{esc(dates[0])}" max="{esc(dates[-1])}"></label>
    <button type="button" id="cf-clear" class="btn ghost">Clear filters</button>
  </div>
  <div class="cf-facets">
    <details><summary>Filter providers</summary><div class="checks">{prov_checks}</div></details>
    <details><summary>Filter provisions</summary><div class="checks">{prv_checks}</div></details>
  </div>
</div>"""
    items = "".join(_change_item(c) for c in log)
    return f"""{controls}
<div class="changes" id="cf-list">{items}</div>
<p class="empty" id="cf-empty" hidden>No changes match your filters.</p>"""


def render_site(dataset: dict, out_dir: Path = SITE_DIR) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    n = len(dataset["providers"])
    pages = {
        "index.html": ("Compute provider terms: comparison matrix", render_matrix(dataset), "index",
                        f"An AI's side-by-side reading of {n} providers' public terms. Every value links to its source so you can verify it."),
        "changes.html": ("Change feed", render_changes(dataset), "changes",
                          "Detected changes to tracked documents, newest first."),
        "about.html": ("About & methodology", render_about(dataset), "about", ""),
    }
    for fname, (title, body, active, subtitle) in pages.items():
        (out_dir / fname).write_text(_shell(title, body, active, subtitle), encoding="utf-8")
        written.append(out_dir / fname)
    # One detail page per provider.
    for pmeta in dataset["providers"]:
        fname = f"provider-{pmeta['provider']}.html"
        title = pmeta["provider_name"]
        (out_dir / fname).write_text(
            _shell(title, render_provider(dataset, pmeta), "", "Published terms, citations, and change history."),
            encoding="utf-8",
        )
        written.append(out_dir / fname)

    # Downloadable Excel workbook, linked from the matrix page.
    from .export import write_workbook

    written.append(write_workbook(dataset, out_dir / EXPORT_XLSX))
    return written


_CSS = """
:root{
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--serif:Georgia,"Iowan Old Style","Times New Roman",serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
--bg:#ffffff;--panel:#f5f8fc;--panel-2:#e9eff7;--ink:#16202e;--muted:#586377;--faint:#8892a1;
--line:#e6ebf2;--line-2:#d5dce7;--accent:#1c3f63;--accent-2:#274f78;--accent-soft:#e9f0f8;
--high:#2f8a52;--medium:#bf851a;--low:#9aa3af;
--disc-bg:#fbf6e9;--disc-line:#efe2c2;--disc-fg:#6a5a20;
--old-bg:#fbeaea;--old-fg:#7a1f1f;--new-bg:#e9f6ec;--new-fg:#1f5a2e;
--shadow:0 1px 2px rgba(20,30,45,.04),0 10px 28px rgba(20,30,45,.06);
}
@media (prefers-color-scheme: dark){:root{
--bg:#0e131a;--panel:#151c26;--panel-2:#1c2531;--ink:#e8edf4;--muted:#9aa4b2;--faint:#727c8b;
--line:#212b38;--line-2:#2b3644;--accent:#7fb0e6;--accent-2:#a3c8f2;--accent-soft:#182636;
--high:#49b678;--medium:#dca63e;--low:#6a7382;
--disc-bg:#221d10;--disc-line:#3a3016;--disc-fg:#d7c690;
--old-bg:#2e1a1a;--old-fg:#e6a2a2;--new-bg:#16281c;--new-fg:#8fd6a5;
--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 28px rgba(0,0,0,.4);
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;color:var(--ink);background:var(--bg);font-family:var(--sans);
font-size:15.5px;line-height:1.62;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1220px;margin:0 auto;padding:0 24px}
a{color:var(--accent-2);text-decoration:none}
a:hover{text-decoration:underline}

/* Header */
.site-head{border-bottom:1px solid var(--line);background:var(--bg)}
.site-head .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:66px}
.brand{display:flex;align-items:center;gap:11px}
.brand:hover{text-decoration:none}
.emblem{color:var(--accent);flex:0 0 auto;box-shadow:var(--shadow);border-radius:7px}
.wordmark{display:block;font-family:var(--serif);color:var(--faint);font-size:11px;font-weight:600;
letter-spacing:.14em;text-transform:uppercase;line-height:1.35}
.wordmark-2{display:block;color:var(--ink);font-size:19px;letter-spacing:.005em;text-transform:none}
.nav{display:flex;gap:22px}
.nav a{color:var(--muted);font-weight:500;font-size:14.5px;padding:4px 0;border-bottom:2px solid transparent}
.nav a.active{color:var(--ink);border-bottom-color:var(--accent)}
.nav a:hover{color:var(--ink);text-decoration:none}

/* Disclaimer */
.disclaimer{background:var(--disc-bg);border-bottom:1px solid var(--disc-line);color:var(--disc-fg);font-size:13px}
.disclaimer .wrap{padding:10px 24px;display:flex;gap:10px;align-items:flex-start}
.disc-icon{flex:0 0 auto;width:17px;height:17px;border-radius:50%;background:var(--disc-fg);color:var(--disc-bg);
font-style:italic;font-weight:700;font-family:var(--serif);font-size:12px;line-height:17px;text-align:center;margin-top:1px}

/* Headings */
main.wrap{padding-top:30px;padding-bottom:72px}
h1{font-family:var(--serif);font-weight:600;font-size:29px;letter-spacing:-.01em;margin:0 0 6px}
.subtitle{color:var(--muted);margin:0 0 26px;font-size:16px;max-width:70ch}
h2{font-family:var(--serif);font-weight:600;font-size:21px;margin:34px 0 12px}
h3{font-size:12px;margin:22px 0 8px;color:var(--faint);text-transform:uppercase;letter-spacing:.08em;font-weight:700}
p{max-width:74ch}

/* Filters + toolbar */
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;margin-bottom:14px}
.filters details{border:1px solid var(--line-2);border-radius:10px;padding:9px 13px;background:var(--panel)}
.filters details[open]{box-shadow:var(--shadow)}
.filters summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--ink)}
.checks{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:10px;max-width:820px}
.checks label{font-size:13px;color:var(--muted);display:flex;gap:6px;align-items:center;cursor:pointer}
.checks input{accent-color:var(--accent)}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;margin:0 0 14px}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:6px 15px;font-size:12.5px;color:var(--muted)}
.legend-lbl{font-weight:700;text-transform:uppercase;letter-spacing:.07em;font-size:11px;color:var(--faint)}
.lg{display:inline-flex;align-items:center;gap:6px}
.hint{font-size:12.5px;color:var(--faint)}

/* Matrix */
.table-scroll{overflow:auto;max-height:80vh;border:1px solid var(--line-2);border-radius:13px;
box-shadow:var(--shadow);background:var(--bg)}
table.matrix{border-collapse:separate;border-spacing:0;width:100%;min-width:940px}
.matrix th,.matrix td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);
vertical-align:top;text-align:left;padding:12px 14px}
.matrix thead th{position:sticky;top:0;z-index:3;background:var(--panel-2);font-size:13.5px;font-weight:700;
color:var(--ink);border-bottom:2px solid var(--line-2)}
.matrix th.corner{left:0;z-index:5;font-family:var(--serif);font-weight:600}
.matrix th.dim-col{position:sticky;left:0;z-index:2;background:var(--panel);min-width:186px;max-width:206px;
font-size:13.5px;font-weight:600;color:var(--ink)}
.matrix th.prov-col a{color:var(--accent-2);font-weight:700}
.matrix tbody tr:hover td.cell{background:var(--accent-soft)}
.matrix td.cell{min-width:236px;max-width:290px;background:var(--bg);transition:background .12s}
.matrix tr.grouprow th.groupcell{position:sticky;left:0;background:var(--panel-2);color:var(--accent-2);
font-family:var(--serif);font-weight:700;font-size:12.5px;text-transform:uppercase;letter-spacing:.09em;
padding:8px 14px;border-bottom:1px solid var(--line-2);border-right:0}
.cell-head{display:flex;gap:8px;align-items:flex-start}
.toggle{border:0;background:none;text-align:left;font:inherit;color:var(--ink);cursor:pointer;padding:0;line-height:1.5}
.toggle:hover{color:var(--accent-2)}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 9px;margin-top:6px}
.dot.high{background:var(--high)}.dot.medium{background:var(--medium)}.dot.low{background:var(--low)}
.dot.verified{background:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
.detail{margin-top:10px;padding:10px 12px;border-left:3px solid var(--accent);background:var(--panel);
border-radius:0 8px 8px 0;font-size:13px}
.detail .full{color:var(--ink)}
.detail .cite{color:var(--muted);font-style:italic;margin-top:7px}
.detail .prog,.prog{margin-top:8px;background:var(--accent-soft);border-radius:7px;padding:7px 9px;font-size:12.5px}
.detail .src,.src{margin-top:8px;font-size:12px;color:var(--muted)}
.detail .meta{margin-top:8px;display:flex;gap:8px;align-items:center}
.badge.verified{background:var(--accent);color:#fff;border-radius:5px;padding:1px 7px;font-size:11px;font-weight:600}
.conf-label{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.cell.empty{color:var(--faint);text-align:center;font-style:italic;background:var(--bg)}
.genline{color:var(--faint);font-size:12.5px;margin-top:14px}

/* Lists, tags, code */
ul.coverage{padding-left:20px}
ul.coverage li{margin-bottom:7px}
.tag{display:inline-block;background:var(--panel-2);border:1px solid var(--line-2);border-radius:5px;
padding:1px 7px;font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:600}
code{background:var(--panel-2);border:1px solid var(--line-2);border-radius:5px;padding:0 5px;font-size:12px;font-family:var(--mono)}

/* Provider pages */
.pdim{border:1px solid var(--line-2);border-radius:12px;padding:16px 18px;margin:12px 0;background:var(--bg);box-shadow:var(--shadow)}
.pdim h3{margin:0 0 9px;font-size:16px;color:var(--ink);text-transform:none;letter-spacing:0;font-weight:700;
font-family:var(--sans);display:flex;align-items:center;gap:9px}
.pval{margin:0 0 8px;max-width:none}
.cite{color:var(--muted);font-style:italic}
.ovnote{margin-top:7px;font-size:12.5px;color:var(--accent-2)}
.empty{color:var(--muted);background:var(--panel);border:1px solid var(--line-2);border-radius:12px;padding:20px}

/* Change feed */
.changes{display:flex;flex-direction:column;gap:14px}
.change{border:1px solid var(--line-2);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.chead{display:flex;gap:9px;align-items:center;flex-wrap:wrap;font-family:var(--serif)}
.cdate{margin-left:auto;color:var(--faint);font-size:13px;font-family:var(--sans)}
.cmeta{color:var(--muted);font-size:12.5px;margin:5px 0 9px}
.cblock{margin:6px 0;font-size:13px;font-family:var(--mono)}
.cblock .old{background:var(--old-bg);color:var(--old-fg);border-radius:6px;padding:4px 7px;margin-bottom:4px}
.cblock .new{background:var(--new-bg);color:var(--new-fg);border-radius:6px;padding:4px 7px}
.ai-note{background:var(--accent-soft);border:1px solid var(--line-2);border-left:3px solid var(--accent);
border-radius:0 8px 8px 0;padding:9px 12px;margin:8px 0}
.ai-note p{margin:5px 0;font-size:13.5px;max-width:none}
.ai-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--accent-2)}
.ai-verify{font-size:11.5px;font-style:italic;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0 2px}
.chip{background:var(--bg);border:1px solid var(--line-2);border-radius:20px;padding:1px 10px;
font-size:11.5px;color:var(--accent-2);font-weight:600}
.cf-controls{margin:0 0 20px;display:flex;flex-direction:column;gap:10px}
.cf-row{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:center}
.cf-row label{font-size:13px;color:var(--muted);display:flex;gap:6px;align-items:center}
.cf-row select,.cf-row input[type=date]{font:inherit;font-size:13px;padding:6px 9px;
border:1px solid var(--line-2);border-radius:8px;background:var(--bg);color:var(--ink)}
.cf-facets{display:flex;flex-wrap:wrap;gap:12px}
.cf-facets details{border:1px solid var(--line-2);border-radius:10px;padding:9px 13px;background:var(--panel)}
.cf-facets details[open]{box-shadow:var(--shadow)}
.cf-facets summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--ink)}

/* Footer */
.site-foot{border-top:1px solid var(--line);color:var(--faint);font-size:13px;margin-top:52px}
.site-foot .wrap{padding:22px 24px}

/* Actions bar, buttons, last-updated */
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 18px}
.btn{display:inline-flex;align-items:center;gap:7px;background:var(--accent);color:#fff;
border:1px solid var(--accent);border-radius:9px;padding:8px 14px;font-size:13.5px;font-weight:600;
cursor:pointer;text-decoration:none;font-family:var(--sans)}
.btn:hover{background:var(--accent-2);border-color:var(--accent-2);text-decoration:none}
.btn.ghost{background:transparent;color:var(--accent-2)}
.btn.ghost:hover{background:var(--accent-soft)}
.updated{margin-left:auto;color:var(--faint);font-size:12.5px}
.col-updated{display:block;margin-top:3px;font-weight:400;font-size:11px;color:var(--faint);
letter-spacing:0;text-transform:none}

/* Print / Save as PDF: hide chrome, expand full values, fit to landscape paper */
@media print{
@page{size:landscape;margin:12mm}
.site-head,.filters,.actions,.toolbar,.site-foot,.genline{display:none!important}
.disclaimer{background:#fff!important;border:0;color:#000}
.disclaimer .wrap{padding:0 0 8px}.disc-icon{display:none}
body{color:#000;background:#fff;font-size:10px}
.wrap{max-width:none;padding:0}
h1{font-size:18px;margin:0 0 2px}.subtitle{font-size:11px;margin:0 0 10px}
.table-scroll{overflow:visible;max-height:none;border:1px solid #999;border-radius:0;box-shadow:none}
table.matrix{min-width:0;width:100%;font-size:9px}
.matrix th,.matrix td{padding:5px 6px;border-color:#bbb}
.matrix thead th{background:#eee!important;color:#000;position:static}
.matrix th.dim-col{position:static;background:#f5f5f5!important;min-width:0}
.matrix tr.grouprow th.groupcell{position:static;background:#e5e5e5!important;color:#000}
.matrix tbody tr:hover td.cell{background:transparent}
.toggle{display:none!important}
.detail{display:block!important;border:0;background:transparent;padding:2px 0 0;color:#000}
.detail .meta{display:none}.detail .src,.detail .cite{color:#333}
.matrix td.cell,.matrix th.dim-col{max-width:none}
tr,.change,.pdim{page-break-inside:avoid}
}

@media(max-width:680px){
.wrap{padding:0 16px}.nav{gap:15px}.wordmark-2{font-size:17px}
h1{font-size:24px}.matrix td.cell{min-width:210px}.table-scroll{max-height:74vh}
.updated{margin-left:0}
}
"""

_JS = """
document.addEventListener('click',function(e){
  var t=e.target.closest('.toggle'); if(!t) return;
  var cell=t.closest('.cell'); var d=cell.querySelector('.detail');
  var open=d.hasAttribute('hidden');
  if(open){d.removeAttribute('hidden');t.setAttribute('aria-expanded','true');}
  else{d.setAttribute('hidden','');t.setAttribute('aria-expanded','false');}
});
function applyFilters(){
  var provs=[].slice.call(document.querySelectorAll('.f-prov')).filter(c=>c.checked).map(c=>c.value);
  var dims=[].slice.call(document.querySelectorAll('.f-dim')).filter(c=>c.checked).map(c=>c.value);
  document.querySelectorAll('.matrix th.prov-col,.matrix td.cell').forEach(function(el){
    el.style.display = provs.indexOf(el.dataset.provider)>=0 ? '' : 'none';
  });
  document.querySelectorAll('.matrix tbody tr[data-dim]').forEach(function(tr){
    tr.style.display = dims.indexOf(tr.dataset.dim)>=0 ? '' : 'none';
  });
  document.querySelectorAll('.matrix tr.grouprow').forEach(function(gr){
    var g=gr.dataset.group;
    var any=[].slice.call(document.querySelectorAll('.matrix tr[data-dim][data-group="'+g+'"]'))
      .some(function(tr){return tr.style.display!=='none';});
    gr.style.display = any ? '' : 'none';
  });
}
document.addEventListener('change',function(e){
  if(e.target.classList.contains('f-prov')||e.target.classList.contains('f-dim')) applyFilters();
});

// Change-feed: sort + filter by provider, date range, and provision.
(function(){
  var list=document.getElementById('cf-list');
  if(!list) return;
  var items=[].slice.call(list.querySelectorAll('.change'));
  var totalDim=document.querySelectorAll('.cf-dim').length;
  function checked(cls){return [].slice.call(document.querySelectorAll(cls)).filter(function(c){return c.checked;}).map(function(c){return c.value;});}
  function apply(){
    var provs=checked('.cf-prov'), dims=checked('.cf-dim');
    var from=document.getElementById('cf-from').value, to=document.getElementById('cf-to').value;
    var sort=document.getElementById('cf-sort').value;
    var dimsNarrowed=dims.length<totalDim, visible=0;
    items.forEach(function(a){
      var show=true;
      if(provs.indexOf(a.dataset.provider)<0) show=false;
      if(from && a.dataset.date<from) show=false;
      if(to && a.dataset.date>to) show=false;
      if(dimsNarrowed){
        var ad=(a.dataset.dims||'').split(' ').filter(Boolean);
        if(!ad.some(function(d){return dims.indexOf(d)>=0;})) show=false;
      }
      a.style.display=show?'':'none'; if(show) visible++;
    });
    items.slice().sort(function(x,y){
      if(sort==='prov'){var c=(x.dataset.pname||'').localeCompare(y.dataset.pname||''); return c||(y.dataset.date).localeCompare(x.dataset.date);}
      if(sort==='date-asc') return (x.dataset.date).localeCompare(y.dataset.date);
      return (y.dataset.date).localeCompare(x.dataset.date);
    }).forEach(function(a){list.appendChild(a);});
    document.getElementById('cf-empty').hidden=visible>0;
  }
  document.addEventListener('change',function(e){
    if(e.target.matches('.cf-prov,.cf-dim,#cf-sort,#cf-from,#cf-to')) apply();
  });
  document.getElementById('cf-clear').addEventListener('click',function(){
    document.querySelectorAll('.cf-prov,.cf-dim').forEach(function(c){c.checked=true;});
    document.getElementById('cf-from').value=''; document.getElementById('cf-to').value='';
    document.getElementById('cf-sort').value='date-desc'; apply();
  });
  apply();
})();
"""
