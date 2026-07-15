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

_CONF_LABEL = {"high": "high", "medium": "medium", "low": "low", "verified": "verified"}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


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
<style>{_CSS}</style>
</head>
<body>
<header class="site-head">
  <div class="wrap">
    <div class="brand"><a href="index.html">Compute Contract Terms Observatory</a></div>
    <nav class="nav">{nav}</nav>
  </div>
</header>
<div class="disclaimer"><div class="wrap"><strong>Not legal advice.</strong>
  An informational comparison of published documents, with citations. Documents change and
  automated extraction can be wrong or stale — review the current source documents yourself.</div></div>
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
        f'<a href="provider-{esc(p["provider"])}.html">{esc(p["provider_name"])}</a></th>'
        for p in providers
    )
    rows = []
    for d in dims:
        cells = []
        for p in providers:
            field = matrix.get(p["provider"], {}).get(d["key"])
            if field is None:
                cells.append(f'<td class="cell empty" data-provider="{esc(p["provider"])}" data-dim="{esc(d["key"])}">—</td>')
            else:
                cells.append(_cell(p["provider"], d["key"], field))
        rows.append(
            f'<tr data-dim="{esc(d["key"])}"><th class="dim-col" title="{esc(d["guidance"])}">{esc(d["label"])}</th>{"".join(cells)}</tr>'
        )

    gen = dataset.get("generated_at", "")[:16].replace("T", " ")
    return f"""
<div class="filters">
  <details open><summary>Filter providers</summary><div class="checks">{prov_checks}</div></details>
  <details><summary>Filter dimensions</summary><div class="checks">{dim_checks}</div></details>
  <div class="hint">Click any cell to see the full value, citation, source document, and fetch date.</div>
</div>
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
        f"<li><strong>{esc(p['provider_name'])}</strong> — "
        + ", ".join(esc(doc["name"]) for doc in p["documents"])
        + "</li>"
        for p in providers
    )
    dim_list = "".join(f"<li><strong>{esc(d['label'])}</strong>: {esc(d['guidance'])}</li>" for d in dims)
    return f"""
<h2>What this is</h2>
<p>An informational, citation-first comparison of the <em>published</em> legal terms of
cloud and GPU compute providers — their terms of service, SLAs, acceptable use policies,
and AI-specific terms. It states what documents say. It does not advise, recommend, or rate.</p>

<h2>Methodology</h2>
<ul>
<li><strong>Archival.</strong> Every fetched document version is preserved with a timestamp and content hash; nothing is overwritten.</li>
<li><strong>Extraction.</strong> A structured pass with Claude (Opus) reads each provider's documents against a fixed 10-term schema, returning a value, a confidence level, and a citation for every field. Values it cannot support are recorded as “not specified” or “unclear” — never guessed.</li>
<li><strong>Human verification.</strong> Extractions can be corrected; corrected fields are marked human-verified and survive re-extraction.</li>
<li><strong>Provenance.</strong> Every value links to its source document, with the fetch date and version hash behind it.</li>
</ul>

<h2>Coverage</h2>
<h3>Providers &amp; documents</h3>
<ul class="coverage">{prov_list}</ul>
<h3>Term dimensions</h3>
<ul class="coverage">{dim_list}</ul>

<h2>Disclaimer</h2>
<p>{esc(dataset.get("disclaimer",""))} Nothing here creates an attorney–client relationship.</p>
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
                        f'(<a href="{esc(prog["citation_url"])}" target="_blank" rel="noopener">program page</a>) — {esc(prog.get("note",""))}</div>')
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
        change_html = '<p class="empty">No changes detected yet — the current snapshots are the baseline.</p>'

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
    return f"""
<article class="change">
  <div class="chead"><strong>{esc(c["provider_name"])}</strong> — {esc(c["document"])}
    <span class="tag">{esc(c["doc_type"])}</span>
    <span class="cdate">{esc(c["detected_at"][:10])}</span></div>
  <div class="cmeta">+{c.get("added_lines",0)} / −{c.get("removed_lines",0)} lines ·
    <a href="{esc(c["url"])}" target="_blank" rel="noopener">source</a></div>
  {blocks}
</article>"""


def render_changes(dataset: dict) -> str:
    log = dataset.get("change_log", [])
    if not log:
        return """
<p class="empty">No document changes detected yet. This feed is the observatory's heartbeat —
once a provider edits a tracked document, the change (with short before/after excerpts) appears
here in reverse-chronological order. The current run establishes the baseline.</p>"""
    return f'<div class="changes">{"".join(_change_item(c) for c in log)}</div>'


def render_site(dataset: dict, out_dir: Path = SITE_DIR) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    n = len(dataset["providers"])
    pages = {
        "index.html": ("Compute provider terms — comparison matrix", render_matrix(dataset), "index",
                        f"What {n} cloud & GPU providers' published terms say, side by side."),
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
    return written


_CSS = """
:root{--fg:#1a1f2b;--muted:#5c6675;--line:#e2e6ec;--bg:#fff;--panel:#f7f9fc;--accent:#1f4e79;
--high:#2e7d46;--medium:#c98a1b;--low:#9aa3af;--verified:#1f4e79;}
*{box-sizing:border-box}
body{margin:0;color:var(--fg);background:var(--bg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
a{color:var(--accent)}
.site-head{border-bottom:1px solid var(--line);background:var(--bg)}
.site-head .wrap{display:flex;align-items:center;justify-content:space-between;height:60px}
.brand a{font-weight:700;color:var(--fg);text-decoration:none;font-size:16px}
.nav a{margin-left:18px;color:var(--muted);text-decoration:none;font-weight:500}
.nav a.active,.nav a:hover{color:var(--accent)}
.disclaimer{background:#fbf7e9;border-bottom:1px solid #f0e6c8;font-size:13px;color:#6b5a1f}
.disclaimer .wrap{padding:8px 20px}
main.wrap{padding-top:24px;padding-bottom:60px}
h1{font-size:24px;margin:0 0 4px}
.subtitle{color:var(--muted);margin:0 0 20px}
h2{font-size:19px;margin:28px 0 10px}
h3{font-size:15px;margin:18px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.filters{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;margin-bottom:16px}
.filters details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--panel)}
.filters summary{cursor:pointer;font-weight:600;font-size:13px}
.checks{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px;max-width:760px}
.checks label{font-size:13px;color:var(--muted);display:flex;gap:5px;align-items:center}
.hint{font-size:12px;color:var(--muted);align-self:center}
.table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table.matrix{border-collapse:collapse;width:100%;min-width:900px}
.matrix th,.matrix td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);
vertical-align:top;text-align:left;padding:10px 12px}
.matrix thead th{position:sticky;top:0;background:var(--panel);z-index:2;font-size:13px}
.matrix th.corner{position:sticky;left:0;z-index:3}
.matrix th.dim-col{position:sticky;left:0;background:var(--panel);z-index:1;min-width:180px;max-width:200px;font-size:13px}
.matrix td.cell{min-width:230px;max-width:280px}
.cell-head{display:flex;gap:7px;align-items:flex-start}
.toggle{border:0;background:none;text-align:left;font:inherit;color:var(--fg);cursor:pointer;padding:0}
.toggle:hover{color:var(--accent)}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 9px;margin-top:5px}
.dot.high{background:var(--high)}.dot.medium{background:var(--medium)}.dot.low{background:var(--low)}
.dot.verified{background:var(--verified);box-shadow:0 0 0 2px #cddcec}
.detail{margin-top:8px;padding-top:8px;border-top:1px dashed var(--line);font-size:13px}
.detail .full{color:var(--fg)}
.detail .cite{color:var(--muted);font-style:italic;margin-top:6px}
.detail .prog{margin-top:6px;background:#eef3f9;border-radius:6px;padding:6px 8px}
.detail .src{margin-top:6px;font-size:12px;color:var(--muted)}
.detail .meta{margin-top:6px;display:flex;gap:8px;align-items:center}
.badge.verified{background:var(--verified);color:#fff;border-radius:4px;padding:1px 6px;font-size:11px}
.conf-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.cell.empty{color:var(--low);text-align:center}
.genline{color:var(--muted);font-size:12px;margin-top:12px}
ul.coverage li{margin-bottom:6px}
.site-foot{border-top:1px solid var(--line);color:var(--muted);font-size:13px;margin-top:40px}
.site-foot .wrap{padding:18px 20px}
.tag{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:4px;
padding:0 6px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
code{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:12px}
.pdim{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;background:var(--bg)}
.pdim h3{margin:0 0 8px;font-size:15px;color:var(--fg);text-transform:none;letter-spacing:0;display:flex;align-items:center;gap:8px}
.pval{margin:0 0 8px}
.cite{color:var(--muted);font-style:italic}
.prog{margin-top:8px;background:#eef3f9;border-radius:6px;padding:8px 10px;font-size:13px}
.src{margin-top:8px;font-size:12px;color:var(--muted)}
.ovnote{margin-top:6px;font-size:12px;color:var(--accent)}
.empty{color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
.changes{display:flex;flex-direction:column;gap:14px}
.change{border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.chead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cdate{margin-left:auto;color:var(--muted);font-size:13px}
.cmeta{color:var(--muted);font-size:12px;margin:4px 0 8px}
.cblock{margin:6px 0;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.cblock .old{background:#fbeaea;color:#7a1f1f;border-radius:4px;padding:3px 6px;margin-bottom:3px}
.cblock .new{background:#e9f6ec;color:#1f5a2e;border-radius:4px;padding:3px 6px}
.matrix th.prov-col a{color:var(--accent);text-decoration:none}
.matrix th.prov-col a:hover{text-decoration:underline}
@media(max-width:640px){.matrix td.cell{min-width:200px}.nav a{margin-left:12px}}
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
  document.querySelectorAll('.matrix tbody tr').forEach(function(tr){
    tr.style.display = dims.indexOf(tr.dataset.dim)>=0 ? '' : 'none';
  });
}
document.addEventListener('change',function(e){
  if(e.target.classList.contains('f-prov')||e.target.classList.contains('f-dim')) applyFilters();
});
"""
