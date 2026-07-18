"""Static site generator. Renders the comparison dataset to plain HTML files in
site/ — no framework, no external assets, no tracking, so it hosts on GitHub Pages
and also opens straight from disk. CSS/JS are inlined via a shared shell.

Step 4 renders the matrix view and the About page. Provider detail pages and the
change feed are added in the next step; the shell and nav already anticipate them.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .schema import is_applicable

SITE_DIR = Path("site")
BRAND = "Compute Terms Observatory"
EXPORT_XLSX = "compute-terms-observatory.xlsx"
# Per-section workbooks (one segment each, respecting the per-segment dimension sets).
EXPORT_XLSX_SEG = {
    "cloud": "compute-terms-cloud-infrastructure.xlsx",
    "closed": "compute-terms-closed-api.xlsx",
    "open": "compute-terms-open-weight.xlsx",
}
EXPORT_XLSX_SEG_TITLE = {
    "cloud": "Cloud Infrastructure Providers",
    "closed": "Closed API AI Model Providers",
    "open": "Open Weight AI Model Providers",
}
# Column order for the Cloud Infrastructure table: hyperscalers first (contiguous),
# then neoclouds by prominence. EDIT THIS LIST to re-order. Any cloud provider not
# listed falls to the end in registry order. (Flagged for confirmation.)
CLOUD_COLUMN_ORDER = [
    "aws", "azure", "gcp",                                        # hyperscalers
    "coreweave", "lambda", "crusoe", "together", "baseten", "runpod", "vast",  # neoclouds
]

# Phase C gate, released in Phase D: the data-protection and accountability groups
# are now rendered behind the progressive-disclosure view switcher below.
RENDER_NEW_GROUPS = False
_HIDDEN_GROUPS = (set() if RENDER_NEW_GROUPS
                  else {"Data protection & privacy", "Accountability & transparency"})


def _visible_dims(dims):
    """Dimensions rendered on the site (drops the gated new groups until Phase D)."""
    return [d for d in dims if d.get("group") not in _HIDDEN_GROUPS]


# ---------------------------------------------------------------------------
# Progressive disclosure (Phase D).
#
# The matrix carries 29 dimensions, which is too many to scan cold. The default
# view therefore shows a curated subset of each group ("key terms"), with a
# per-group expander to reveal the rest. The view pills always show their whole
# group, so nothing is reachable only through the expander.
#
# DEFAULT_VIEW_DIMS is the editable curation: add or remove keys here and the
# default view, its expander counts, and the view-scoped exports all follow.
# Reviewed and approved 2026-07-18.
# ---------------------------------------------------------------------------

DEFAULT_VIEW_DIMS = [
    # General contract terms (5 of 15)
    "data_use_ai_training",
    "liability",
    "output_indemnity",
    "termination",
    "unilateral_modification",
    # Service level (SLA) terms (3 of 4)
    "availability_definition",
    "credit_regime",
    "claim_mechanics",
    # Data protection & privacy (3 of 5)
    "data_residency",
    "data_transfer_mechanism",
    "content_retention_review",
    # Accountability & transparency (3 of 5)
    "prohibited_high_risk_uses",
    "appeal_redress",
    "eu_ai_act_role",
]

# The view switcher. Each view names the dimension groups it renders in full;
# the default "key" view renders DEFAULT_VIEW_DIMS across every group instead.
from .schema import (  # noqa: E402  (grouped with the view config it feeds)
    GROUP_ACCOUNTABILITY,
    GROUP_GENERAL,
    GROUP_PRIVACY,
    GROUP_SLA,
)

VIEWS = [
    ("key", "Key terms", None),
    ("all", "All terms", (GROUP_GENERAL, GROUP_SLA, GROUP_PRIVACY, GROUP_ACCOUNTABILITY)),
    ("core", "Core contract", (GROUP_GENERAL, GROUP_SLA)),
    ("privacy", "Privacy & data protection", (GROUP_PRIVACY,)),
    ("accountability", "Accountability & transparency", (GROUP_ACCOUNTABILITY,)),
]
VIEW_GROUPS = {key: groups for key, _label, groups in VIEWS}
DEFAULT_VIEW = "key"


def view_dims(dims, view: str):
    """The dimensions a given view renders, in schema order."""
    if view == "key":
        keys = set(DEFAULT_VIEW_DIMS)
        return [d for d in dims if d["key"] in keys]
    groups = VIEW_GROUPS.get(view) or ()
    return [d for d in dims if d.get("group") in groups]


def seg_xlsx_name(group: str, view: str) -> str:
    """Per-section workbook filename, scoped to the active view. The 'all' view
    keeps the original name so existing links stay good."""
    base = EXPORT_XLSX_SEG[group]
    if view == "all":
        return base
    return base[: -len(".xlsx")] + f"-{view}.xlsx"
# Custom domain for GitHub Pages. Written into the build as a CNAME file so that
# Actions deploys keep the custom domain (a deploy without it would clear the
# Pages custom-domain setting).
CUSTOM_DOMAIN = "www.computeterms.ai"

_CONF_LABEL = {"high": "high", "medium": "medium", "low": "low", "verified": "verified"}

# The bespoke "O." brand mark (a chunky organic letter O with a detached dot,
# reading as a period and, at size, a magnifier). Its vector source is a reserved
# brand asset kept OUT of this public repo: it is loaded at build time from the
# private brand store (data/brand.json). When that asset is absent (a code-only
# build) a neutral geometric ring+dot placeholder is used instead.
def _load_brand_mark():
    p = Path("data/brand.json")
    if p.exists():
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
            if b.get("mark_o") and b.get("mark_dot"):
                return b["mark_o"], b["mark_dot"]
        except (ValueError, OSError):
            pass
    return (
        '<path fill-rule="evenodd" d="M46,12 a34,34 0 1 0 0.1,0 Z M46,30 a16,16 0 1 0 0.1,0 Z"/>',
        '<circle cx="83" cy="83" r="9"/>',
    )


_MARK_O, _MARK_DOT = _load_brand_mark()


def _brand_mark(color: str = "#14120f", cls: str = "", title: str = "") -> str:
    """The O. mark as inline SVG in a single color. `cls` sets a CSS class for
    sizing; `title` adds an accessible label (else the mark is decorative)."""
    c = f' class="{cls}"' if cls else ""
    a = f'<title>{esc(title)}</title>' if title else ' aria-hidden="true"'
    return (f'<svg{c} viewBox="0 0 100 100" fill="{color}" xmlns="http://www.w3.org/2000/svg">'
            f'{a}{_MARK_O}{_MARK_DOT}</svg>')


# The favicon is the standalone O. glyph (ink), inline data URI, legible at 16px.
_FAVICON = "data:image/svg+xml," + urllib.parse.quote(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' fill='#14120f'>"
    + _MARK_O + _MARK_DOT + "</svg>"
)


def esc(s) -> str:
    # House style (CLAUDE.md): no em/en dashes in any site copy. Sanitize at the
    # render boundary so dashes from model output, notes, or citations never leak
    # into the page.
    text = str(s if s is not None else "").replace("—", "-").replace("–", "-")
    return html.escape(text)


def _wordmark() -> str:
    """The O.bservatory lockup: 'COMPUTE TERMS' eyebrow, then the bespoke O. mark
    reading straight into 'bservatory' set in the rounded display face."""
    return (
        '<span class="wm-eyebrow">Compute Terms</span>'
        f'<span class="wm-word">{_brand_mark(cls="wm-o")}<span class="wm-txt">bservatory</span></span>'
    )


# The serif-italic deck line. Only the lead phrase links to the methodology. A short
# variant is shown on narrow viewports (item 5), the full sentence on desktop.
_DECK_LINK = '<a href="methodology.html">AI-generated summaries of public terms</a>'
_DECK_HTML = (
    f'<span class="deck-full">{_DECK_LINK} of cloud infrastructure providers and AI '
    'model providers, not legal advice. Every value links to its source.</span>'
    f'<span class="deck-short">{_DECK_LINK}, not legal advice.</span>'
)


def _sic(citation: str) -> str:
    """Cohere's published Terms of Use genuinely contain the typo 'OFFERINfGS'
    (verified in the raw HTML capture, not a normalization artifact). Flag it with
    [sic] at the display layer only; the stored quote stays verbatim (Issue 13)."""
    return (citation or "").replace("OFFERINfGS", "OFFERINfGS [sic]")


def _mark_state(caption: str, link_href: str = "", link_text: str = "") -> str:
    """A character-free empty/404 state: the muted O. glyph + one serif-italic line."""
    link = (f'<p class="ms-link"><a href="{esc(link_href)}">{esc(link_text)}</a></p>'
            if link_href else "")
    return f'<div class="mark-state">{_brand_mark()}<p>{esc(caption)}</p>{link}</div>'


def _shell(title: str, body: str, active: str, subtitle: str = "",
           hide_title: bool = False, home: bool = False) -> str:
    nav_items = [("index.html", "Matrix"), ("changes.html", "Change feed"),
                 ("methodology.html", "Methodology"), ("about.html", "About")]
    nav = "".join(
        f'<a href="{href}" class="{"active" if key==active else ""}">{esc(label)}</a>'
        for href, label in [(h, l) for h, l in nav_items]
        for key in [href.split(".")[0]]
    )
    if hide_title:
        heading = f'<h1 class="sr-only">{esc(title)}</h1>'
    else:
        heading = f'<h1>{esc(title)}</h1>' + (
            f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else '')

    if home:
        # Centered hero: nav only up top, then the big wordmark and the serif deck
        # line beneath it. No masthead band, no box.
        masthead = (
            f'<div class="home-top"><nav class="nav">{nav}</nav></div>'
            '<section class="hero"><div class="hero-in">'
            f'<div class="hero-wm">{_wordmark()}</div>'
            f'<p class="hero-deck">{_DECK_HTML}</p>'
            '</div></section>'
        )
    else:
        # Interior: compact borderless masthead, lockup left, nav right, deck beneath.
        masthead = (
            '<header class="site-head"><div class="wrap">'
            f'<a class="brand" href="index.html" aria-label="{esc(BRAND)} home">{_wordmark()}</a>'
            f'<nav class="nav">{nav}</nav></div></header>'
            f'<div class="deck"><div class="wrap">{_DECK_HTML}</div></div>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | {BRAND}</title>
<link rel="icon" href="{_FAVICON}">
<style>{_CSS}</style>
</head>
<body class="{'is-home' if home else 'is-interior'}">
{masthead}
<main class="wrap">
  {heading}
  {body}
</main>
<footer class="site-foot"><div class="wrap">
  <span class="foot-copy">© 2026 Compute Terms Observatory</span> ·
  Public documents only · Descriptive, never advisory ·
  <a href="methodology.html">Methodology</a> ·
  <a href="https://github.com/erinecrum/compute-terms-observatory">Source</a>
</div></footer>
<script>{_JS}</script>
</body>
</html>"""


def _source_line(source: dict) -> str:
    """Provenance line for a value's source document. Direct/browser fetches show
    the fetch date; wayback-tier documents show the Internet Archive capture date
    (in place of the fetch date) plus a note and, if the capture is stale, a badge."""
    if not source:
        return ""
    link = (f'<a href="{esc(source["url"])}" target="_blank" rel="noopener">'
            f'{esc(source["name"])}</a>')
    if source.get("fetch_method") == "wayback":
        cap = esc((source.get("capture_timestamp", "") or "")[:10])
        stale = ' <span class="badge stale">stale &middot; capture &gt;7 days old</span>' if source.get("stale") else ''
        return (f'<div class="src wayback">Archived capture from <strong>{cap}</strong> '
                f'via the Internet Archive{stale}'
                f'<div class="wb-note">This source blocks automated retrieval, so the observatory '
                f'relies on Internet Archive captures, which may lag the live page.</div>'
                f'Source: {link}</div>')
    return (f'<div class="src">Source: {link} &middot; fetched '
            f'{esc((source.get("fetched_at", "") or "")[:10])}</div>')


# The four honest display states (Issue 2). Everything is AI-reviewed; there is no
# human/counsel-verified tier. Warning styling is reserved for quote_unverified;
# absence states (silent / not applicable) get neutral, muted treatment so they
# read as "nothing to see", not "something went wrong".
_STATUS_META = {
    "quote_verified":   ("ok",     "supporting quote verified against the source document", "ok",    "✓ quote verified"),
    "quote_unverified": ("warn",   "no supporting quote could be matched to the source",     "warn",  "unverified — supporting quote not matched"),
    "no_clause_found":  ("absent", "the provider's terms are silent on this point",          "muted", "silent — no clause found"),
    "not_applicable":   ("na",     "this dimension does not apply to this offering",         "muted", "not applicable"),
}
_DEFAULT_STATUS = "quote_unverified"


def _status_meta(field: dict):
    return _STATUS_META.get(field.get("status", _DEFAULT_STATUS), _STATUS_META[_DEFAULT_STATUS])


def _status_dot(field: dict) -> str:
    """Four-state status indicator. Never color-alone: it carries a descriptive
    title and an aria-label so assistive tech announces the status."""
    status = field.get("status", _DEFAULT_STATUS)
    dot_cls, title, _bc, badge_text = _status_meta(field)
    label = badge_text.lstrip("✓ ").strip()
    if status == "quote_verified":
        c = field.get("confidence", "low")
        c = c if c in ("high", "medium", "low") else "low"
        title = f"{title}; confidence {c}"
        label = f"{label}, confidence {c}"
    return (f'<span class="dot {dot_cls}" role="img" aria-label="Status: {esc(label)}" '
            f'title="{esc(title)}"></span>')


def _cell(provider: str, dim_key: str, field: dict) -> str:
    value = field.get("display_value", field.get("value", ""))
    citation = field.get("citation", "")
    source = field.get("source")
    conf = field.get("confidence", "low")
    status = field.get("status", _DEFAULT_STATUS)
    absent = status in ("no_clause_found", "not_applicable")
    unverified = status == "quote_unverified"
    prog = field.get("commitment_program")

    src_line = _source_line(source)
    cite_line = f'<div class="cite">“{esc(_sic(citation))}”</div>' if citation else ""
    _dc, _t, badge_cls, badge_text = _status_meta(field)
    badge = f'<span class="badge {badge_cls}">{esc(badge_text)}</span>'
    prog_line = ""
    if prog:
        prog_line = (
            f'<div class="prog"><strong>{esc(prog["program"])}:</strong> {esc(prog["value"])} '
            f'(<a href="{esc(prog["citation_url"])}" target="_blank" rel="noopener">program</a>)</div>'
        )

    short = value if len(value) <= 160 else value[:157] + "…"
    cls = "cell unverified" if unverified else ("cell absent" if absent else "cell")
    return f"""<td class="{cls}" data-provider="{esc(provider)}" data-dim="{esc(dim_key)}" data-status="{esc(status)}">
  <div class="cell-head">{_status_dot(field)} <button class="toggle" aria-expanded="false">{esc(short)}</button></div>
  <div class="detail" hidden>
    <div class="full">{esc(value)}</div>
    {cite_line}{prog_line}{src_line}
    <div class="meta">{badge}<span class="conf-label">{esc(_CONF_LABEL.get(conf, conf))}</span></div>
  </div>
</td>"""


def _matrix_table(dims: list, subset: list, matrix: dict, table_id: str) -> str:
    """One comparison matrix (dimensions as rows, the given providers as columns).
    Reused for each section so they all share the existing matrix design."""
    if not subset:
        return '<p class="empty">No entries yet — these populate as their documents are classified.</p>'
    head = "".join(
        f'<th scope="col" class="prov-col" data-provider="{esc(p["provider"])}">'
        f'<a href="provider-{esc(p["provider"])}.html">{esc(p["provider_name"])}</a>'
        f'<span class="col-sub">{esc(p.get("parent_company") or SEG_LABEL.get(p.get("segment",""), ""))}</span>'
        # Item 6: no per-provider "updated" line; the section header's checked stamp
        # is the single freshness indicator. Keep the small "stale" flag only when a
        # provider's capture is stale relative to the corpus.
        + ('<span class="col-stale" title="Some documents are archived via the Internet Archive; the latest capture is over 7 days old">&#9888; stale</span>'
           if p.get("has_stale_capture") else "")
        + '</th>'
        for p in subset
    )
    ncols = len(subset) + 1
    key_set = set(DEFAULT_VIEW_DIMS)

    # Per-group totals drive the "Show all N dimensions" expander: a group only
    # gets one when the default view actually withholds something.
    group_total, group_key = {}, {}
    for d in dims:
        g = d.get("group", "")
        group_total[g] = group_total.get(g, 0) + 1
        if d["key"] in key_set:
            group_key[g] = group_key.get(g, 0) + 1

    def expander(g):
        total, shown = group_total.get(g, 0), group_key.get(g, 0)
        if total <= shown:
            return ""
        return (f'<tr class="exprow" data-group="{esc(g)}"><td class="expcell" colspan="{ncols}">'
                f'<button type="button" class="expbtn" data-expand="{esc(g)}" aria-expanded="false">'
                f'Show all {total} dimensions</button></td></tr>')

    rows, cur = [], None
    for d in dims:
        g = d.get("group", "")
        if g and g != cur:
            if cur is not None:
                rows.append(expander(cur))
            cur = g
            rows.append(f'<tr class="grouprow" data-group="{esc(g)}"><th scope="colgroup" class="groupcell" colspan="{ncols}">{esc(g)}</th></tr>')
        cells = "".join(
            (f'<td class="cell empty" data-provider="{esc(p["provider"])}" data-dim="{esc(d["key"])}">n/a</td>'
             if matrix.get(p["provider"], {}).get(d["key"]) is None
             else _cell(p["provider"], d["key"], matrix[p["provider"]][d["key"]]))
            for p in subset
        )
        keyattr = ' data-key="1"' if d["key"] in key_set else ""
        rows.append(f'<tr data-dim="{esc(d["key"])}" data-group="{esc(g)}"{keyattr}><th scope="row" class="dim-col" title="{esc(d["guidance"])}">{esc(d["label"])}</th>{cells}</tr>')
    if cur is not None:
        rows.append(expander(cur))
    return (f'<div class="table-scroll"><table class="matrix" id="{table_id}">'
            f'<thead><tr><th scope="col" class="corner">Term dimension</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


SEG_LABEL = {"hyperscaler": "Hyperscaler", "neocloud": "Neocloud", "model_provider": "Model provider"}
OPEN_LABEL = {"closed_api": "Closed API", "open_weight": "Open weight"}


def render_matrix(dataset: dict) -> str:
    dims = _visible_dims(dataset["dimensions"])
    providers = dataset["providers"]
    matrix = dataset["matrix"]

    cloud = [p for p in providers if p["segment"] in ("hyperscaler", "neocloud")]
    # Curated column order: hyperscalers first, then neoclouds by prominence.
    _rank = {pid: i for i, pid in enumerate(CLOUD_COLUMN_ORDER)}
    cloud.sort(key=lambda p: (_rank.get(p["provider"], len(_rank)), p["provider_name"]))
    closed = [p for p in providers if p["segment"] == "model_provider" and p.get("openness") == "closed_api"]
    openw = [p for p in providers if p["segment"] == "model_provider" and p.get("openness") == "open_weight"]

    # Per-segment dimension sets: each table renders only its applicable dimensions.
    def dims_for(group):
        return [d for d in dims if is_applicable(group, d["key"])]

    # Attribute map for client-side filtering/sorting (counts, columns).
    pmap = {p["provider"]: {"seg": p["segment"], "open": p.get("openness", ""),
                            "parent": p.get("parent_company", ""), "lic": p.get("license_type", ""),
                            "name": p["provider_name"], "upd": (p.get("last_updated") or "")[:10]}
            for p in providers}

    def facet(cls, items, labels=None):
        labels = labels or {}
        return "".join(
            f'<label><input type="checkbox" class="{cls}" value="{esc(v)}" checked> {esc(labels.get(v, v))}</label>'
            for v in items)

    segs = [s for s in ("hyperscaler", "neocloud", "model_provider") if any(p["segment"] == s for p in providers)]
    opens = [o for o in ("closed_api", "open_weight") if any(p.get("openness") == o for p in providers)]
    parents = sorted({p["parent_company"] for p in providers if p.get("parent_company")})
    lics = sorted({p["license_type"] for p in providers if p.get("license_type")})

    lc = esc((dataset.get("last_checked", {}).get("last_checked_utc", "") or "")[:16].replace("T", " "))
    fresh = f'<span class="sec-fresh">checked {lc} UTC</span>' if lc else ''

    def pill(cls, label, items, labels=None):
        return (f'<details class="pill"><summary>{esc(label)}</summary>'
                f'<div class="checks">{facet(cls, items, labels)}</div></details>')

    # The primary choice: which terms to view. Big pills own segment + openness
    # selection (default: All). The AI Model Providers pill reveals a sub-control.
    chooser = (
        '<div class="chooser" id="chooser">'
        '<div class="chooser-main">'
        '<button type="button" class="cpill" data-choose="cloud">Cloud Infrastructure</button>'
        '<button type="button" class="cpill" data-choose="model">AI Model Providers</button>'
        '<button type="button" class="cpill selected" data-choose="all">All</button>'
        '</div>'
        '<div class="chooser-sub" id="chooser-sub" hidden>'
        '<button type="button" class="spill selected" data-sub="all">All model providers</button>'
        '<button type="button" class="spill" data-sub="closed">Closed API</button>'
        '<button type="button" class="spill" data-sub="open">Open weight</button>'
        '</div></div>'
    )
    # The view switcher: which terms are shown, independent of which providers.
    # "Key terms" (the default) shows the curated subset of every group; the other
    # pills show their group(s) in full.
    viewbar = (
        '<div class="viewbar" id="viewbar" role="group" aria-label="Which terms to show">'
        + "".join(
            f'<button type="button" class="vpill{" selected" if key == DEFAULT_VIEW else ""}" '
            f'data-view="{esc(key)}">{esc(label)}</button>'
            for key, label, _groups in VIEWS
        )
        + '</div>'
    )
    # Slim secondary toolbar: the remaining filters + compare + export, subordinate
    # to the chooser (segment/openness live in the chooser now).
    toolbar = (
        '<div class="toolbar" id="toolbar"><div class="tb-filters">'
        + pill("f-parent", "Parent company", parents)
        + pill("f-lic", "License type", lics)
        + '<button type="button" class="pill pill-btn" id="compare-btn" title="Compare mode">Compare</button>'
        + '</div>'
        + '<details class="pill export-menu"><summary>Export</summary><div class="menu">'
        + f'<a href="{esc(EXPORT_XLSX)}" download>Full workbook (.xlsx)</a>'
        + '<button type="button" onclick="window.print()">Print / save all as PDF</button>'
        + '</div></details></div>'
    )

    def sort_select(table_id):
        return (f'<label class="sec-sort">Sort <select class="sec-sort-sel" data-target="{table_id}">'
                '<option value="name">Name A-Z</option>'
                '<option value="updated">Recently updated</option></select></label>')

    def sec_exports(group, sec_id):
        # The .xlsx link is rewritten client-side to the workbook for the active
        # view, so a download matches what the reader is looking at.
        names = json.dumps({v: seg_xlsx_name(group, v) for v, _l, _g in VIEWS})
        return (f'<a class="sec-x" href="{esc(seg_xlsx_name(group, DEFAULT_VIEW))}" download '
                f"data-xlsx='{esc(names)}' title=\"Download this section as .xlsx\">.xlsx</a>"
                f'<button class="sec-x" type="button" data-print-sec="{sec_id}" title="Print this section">PDF</button>')

    def section(name, group, subset, table_id, sec_id):
        # One-row section header: name + count left; freshness + per-section sort +
        # scoped export right.
        header = (
            f'<div class="sec-head"><h2 class="sec-h">{esc(name)} '
            f'<span class="sec-cnt" data-cnt="{group}">{len(subset)}</span></h2>'
            f'<div class="sec-ctl">{fresh}{sort_select(table_id)}'
            f'<span class="sec-exports">{sec_exports(group, sec_id)}</span></div></div>'
        )
        return (f'<section id="{sec_id}" class="msec" data-sec="{sec_id}">{header}'
                f'{_matrix_table(dims_for(group), subset, matrix, table_id)}</section>')

    grouped = (
        '<div id="grouped-view">'
        + section("Cloud Infrastructure Providers", "cloud", cloud, "tbl-cloud", "cloud-infrastructure")
        + '<div class="mgroup" id="ai-model-providers"><h2 class="mgroup-h">AI Model Providers</h2>'
        + section("Closed API AI Model Providers", "closed", closed, "tbl-closed", "closed-api")
        + section("Open Weight AI Model Providers", "open", openw, "tbl-open", "open-weight")
        + '</div>'
        + '</div><div id="flat-view" hidden></div>'
    )

    # Compare mode: pick 2-3 providers, dimensions render as stacked cards (reuses
    # the same cells + detail component). Toggled from the Compare control.
    cmp_pills = "".join(
        f'<button type="button" class="cmp-pp" data-pid="{esc(p["provider"])}">{esc(p["provider_name"])}</button>'
        for p in providers)
    compare_view = (
        '<div id="compare-view" hidden>'
        '<div class="cmp-pick"><span class="cmp-pick-lbl">Pick 2-3 providers</span>'
        f'<div class="cmp-pick-pills">{cmp_pills}</div></div>'
        f'<div id="cmp-empty">{_mark_state("Choose two or three providers to compare.")}</div>'
        '<div id="cmp-out"></div></div>'
    )

    gen = dataset.get("generated_at", "")[:16].replace("T", " ")
    return f"""
{chooser}
{viewbar}
{toolbar}
{grouped}
{compare_view}
<script>window.CTO_PROVIDERS={json.dumps(pmap)};
window.CTO_VIEW_GROUPS={json.dumps({k: (list(g) if g else None) for k, g in VIEW_GROUPS.items()})};
window.CTO_DIMS={json.dumps([{"key": d["key"], "label": d["label"], "group": d.get("group","")} for d in dims])};</script>
<p class="genline">Generated {esc(gen)} UTC</p>
"""


def render_about(dataset: dict) -> str:
    n = len(dataset["providers"])
    dims = len(dataset["dimensions"])
    faqs = [
        ("What is this?",
         "<p>The Compute Terms Observatory is an automated research tracker that reads the "
         "<em>published</em> terms of cloud infrastructure providers and AI model providers and "
         "lays them out in one comparison matrix. Every value links to the source document it "
         "came from.</p>"),
        ("Where does the data come from?",
         f"<p>Public documents only: terms of service, SLAs, acceptable-use and usage policies, "
         f"model licenses, and deprecation policies for {n} providers across {dims} contract "
         f"dimensions. Each value carries a short verbatim quote and a link to the archived "
         f'source. See the <a href="methodology.html">methodology</a> for the full pipeline and '
         f"coverage.</p>"),
        ("How often is it checked?",
         "<p>An automated workflow re-fetches every tracked document twice daily and archives a "
         "timestamped, content-hashed snapshot. Each section header shows when its corpus was "
         "last checked.</p>"),
        ("Can I rely on it?",
         "<p><em>No, verify before you rely on it.</em> These are an AI's readings of public "
         "terms, not the terms themselves and not legal advice. They can be wrong, incomplete, "
         "or out of date, and public terms are only a starting point; negotiated agreements "
         "routinely differ. Every value links to its source so you can check it yourself. Nothing "
         "here creates an attorney-client relationship.</p>"),
        ("Who runs it?",
         "<p>It is an independent, open-source research project. The code is MIT-licensed and the "
         "brand is reserved. It is not affiliated with, endorsed by, or sponsored by any of the "
         "providers it tracks.</p>"),
        ("How do I report an error?",
         '<p>Open an issue on the <a href="https://github.com/erinecrum/compute-terms-observatory">'
         "source repository</a> with the provider, the dimension, and what you believe is wrong. "
         "Corrections are re-checked against the archived source.</p>"),
    ]
    rows = "".join(
        f'<details class="faq" name="faq"><summary>{esc(q)}'
        f'<span class="faq-ind" aria-hidden="true"></span></summary>'
        f'<div class="faq-a">{a}</div></details>'
        for q, a in faqs
    )
    return f'<div class="faq-list">{rows}</div>'


def _segment_dims_section() -> str:
    """Document, from the applicability map, which dimensions each segment omits and
    why — so the omissions read as editorial judgment, not missing data."""
    from .schema import SEGMENT_GROUP_LABEL, SEGMENT_REMOVED, dimension

    blocks = []
    for group in ("cloud", "closed", "open"):
        removed = SEGMENT_REMOVED.get(group, {})
        if not removed:
            items = "<li>No dimensions are omitted for this segment.</li>"
        else:
            items = "".join(
                f'<li><strong>{esc(dimension(k).label)}</strong> — {esc(reason)}.</li>'
                for k, reason in removed.items()
            )
        blocks.append(
            f'<h3>{esc(SEGMENT_GROUP_LABEL[group])}</h3><ul>{items}</ul>'
        )
    return (
        '<h2 id="dimension-sets">Why the tables differ by segment</h2>'
        '<p>Each segment&rsquo;s table shows only the dimensions that can meaningfully '
        'exist for that entry type. A dimension is omitted only when it is '
        '<em>structurally</em> inapplicable &mdash; the precondition does not exist &mdash; '
        'not merely because today&rsquo;s providers are silent. Collective silence is a '
        'finding and stays (for example, closed-API providers that publish no SLA still '
        'show an availability row, because a service <em>could</em> commit to uptime). '
        'The omissions per segment:</p>'
        + "".join(blocks)
    )


def render_methodology(dataset: dict) -> str:
    """Methodology page — adapted from METHODOLOGY.md to describe this pipeline
    accurately. Reports what the system does; contains no advisory language."""
    return ("""
<h2>How this works</h2>
<p>The Compute Terms Observatory is an automated research tracker of the
<em>published</em> terms of cloud infrastructure providers and AI model families. It works in three stages.</p>
<ol>
<li><strong>Archive.</strong> Twice daily, an automated workflow fetches each tracked
provider's public terms of service, SLAs, acceptable-use and usage policies, model
licenses, and deprecation policies, and archives a normalized text snapshot with a
timestamp and content hash. Fetching uses three tiers in order &mdash; a direct request
as an identified archival agent, a headless browser for JavaScript-rendered pages, and
the Internet Archive as a fallback (dated by capture time) &mdash; and never attempts to
bypass a CAPTCHA or other interactive challenge. A small number of sources block direct
automated retrieval; for those, the archived version is the most recent Internet Archive
capture, dated individually on each value, and may lag the live page. The &ldquo;terms last
checked&rdquo; time on the main page reflects the most recent run of the directly fetched
sources.</li>
<li><strong>Detect.</strong> When a document's normalized text changes between runs, the
system records the localized before/after difference. The change feed is generated from
those differences; quoted excerpts are kept short.</li>
<li><strong>Classify.</strong> When a document changes, an AI model (Claude, by Anthropic)
reads it against a fixed, published schema of contract dimensions and records, for each, a
value and a short <strong>verbatim supporting quote</strong> copied from the document. The
code mechanically checks that the quote actually appears in the archived text. Values whose
quote cannot be verified are published as <strong>&ldquo;unverified&rdquo;</strong> with low
confidence and should be given no weight.</li>
</ol>

{_segment_dims_section()}

<h2 id="status-labels">Reading the status labels</h2>
<p>Every value in the matrix carries one of four labels describing how well it is supported.
Nothing here is human-verified; the labels describe the automated check, not anyone's review.</p>
<ul>
<li><strong>Quote verified.</strong> The value is backed by a short verbatim quote that the
code mechanically found in the archived source text.</li>
<li><strong>Unverified.</strong> The model returned a value but no supporting quote could be
matched to the source. Give it no weight without reading the document yourself.</li>
<li><strong>Silent.</strong> The provider's terms do not address this dimension &mdash; there is
no governing clause to quote. This is a finding about the terms, not a failure of the tool.</li>
<li><strong>Not applicable.</strong> The dimension does not apply to this offering &mdash; for
example, service-level or capacity terms for a downloadable open-weight model, which is a
license rather than a hosted service.</li>
</ul>

<h2>Provenance</h2>
<p>Every value records the document it came from, its source URL, the fetch date, the
archived version's content hash, and the model used, so any datapoint traces back to the
exact text that produced it. License values attach to the specific license document and
model generation they came from; they are never asserted across a whole model family.</p>

<h2>What this is not</h2>
<p>This site reports what public documents say, with citations. It does not characterize,
rate, or recommend, and it gives no advice. It is AI-generated analysis of public documents;
no attorney reviews individual classifications before publication, and classifications may be
wrong, incomplete, or out of date. Public terms are only a starting point &mdash; negotiated
agreements routinely differ from a provider's public documents. Nothing here is legal advice,
and no attorney-client relationship is created by reading it. Read the underlying documents,
which are linked from every datapoint, and consult your own counsel.</p>

<h2>Corrections</h2>
<p>Every datapoint links to its source. Everything here is AI-reviewed — there is no
human-verified tier. A correction can adjust a value or its citation, but the corrected
quote is then re-checked against the archived source exactly like any other value, and
carries no special badge. If you spot an error, open an issue
in the <a href="https://github.com/erinecrum/compute-terms-observatory">source repository</a>.</p>

<h2>Coverage &amp; data</h2>
<p>The code is open source (MIT). The change history is published here as the change feed;
the archived snapshot corpus is maintained in the project's data repository. See the
<a href="about.html">About</a> page for the full provider and dimension coverage.</p>
""").replace("{_segment_dims_section()}", _segment_dims_section())


def render_provider(dataset: dict, pmeta: dict) -> str:
    provider = pmeta["provider"]
    fields = dataset["matrix"].get(provider, {})
    # A provider page shows only the dimensions applicable to its segment.
    group = pmeta.get("group", "cloud")
    dims = [d for d in _visible_dims(dataset["dimensions"]) if is_applicable(group, d["key"])]

    # Documents used, with provenance (fetch tier + date, or IA capture date).
    def _doc_li(d):
        if d.get("fetch_method") == "wayback":
            cap = esc((d.get("capture_timestamp", "") or "")[:10])
            stale = ' <span class="badge stale">stale</span>' if d.get("stale") else ''
            when = f'Internet Archive capture {cap}{stale}'
        else:
            when = f'fetched {esc(d["fetched_at"][:10])}'
        trunc = " · <em>truncated for length</em>" if d.get("truncated") else ""
        return (f'<li><a href="{esc(d["url"])}" target="_blank" rel="noopener">{esc(d["name"])}</a> '
                f'<span class="tag">{esc(d["doc_type"])}</span> · {when} · '
                f'<code>{esc(d["text_sha256"][:12])}</code>{trunc}</li>')
    docs = "".join(_doc_li(d) for d in pmeta.get("documents", []))

    rows = []
    toc = []
    cur_group = None
    for dim in dims:
        f = fields.get(dim["key"])
        if not f:
            continue
        # Group headings (and a grouped TOC) so 29 dimensions stay navigable.
        g = dim.get("group", "")
        if g and g != cur_group:
            cur_group = g
            gid = "grp-" + g.lower().replace(" & ", "-").replace(" ", "-")
            rows.append(f'<h3 class="pgrp" id="{esc(gid)}">{esc(g)}</h3>')
            toc.append(f'<span class="pdim-toc-h">{esc(g)}</span>')
        toc.append(f'<a href="#dim-{esc(dim["key"])}">{esc(dim["label"])}</a>')
        source = f.get("source")
        prog = f.get("commitment_program")
        cite = f'<div class="cite">“{esc(_sic(f.get("citation","")))}”</div>' if f.get("citation") else ""
        src = _source_line(source)
        progline = ""
        if prog:
            progline = (f'<div class="prog"><strong>{esc(prog["program"])}:</strong> {esc(prog["value"])} '
                        f'(<a href="{esc(prog["citation_url"])}" target="_blank" rel="noopener">program page</a>). {esc(prog.get("note",""))}</div>')
        _dc, _t, badge_cls, badge_text = _status_meta(f)
        badge = f'<span class="badge {badge_cls}">{esc(badge_text)}</span>'
        rows.append(f"""
<section class="pdim" id="dim-{esc(dim["key"])}">
  <h4>{_status_dot(f)} {esc(dim["label"])} {badge}</h4>
  <p class="pval">{esc(f.get("display_value", f.get("value","")))}</p>
  {cite}{progline}{src}
</section>""")

    # This provider's change history.
    changes = [c for c in dataset.get("change_log", []) if c["provider"] == provider]
    if changes:
        chitems = "".join(_change_item(c) for c in changes)
        change_html = f'<div class="changes">{chitems}</div>'
    else:
        change_html = '<p class="empty">No changes detected yet. The current snapshots are the baseline.</p>'

    stale_note = (
        '<p class="stale-note">⚠ Some documents for this entry are archived via the '
        'Internet Archive (the provider blocks automated retrieval) and the most recent '
        'capture is over 7 days old, so it may lag the live page.</p>'
        if pmeta.get("has_stale_capture") else ""
    )
    return f"""
<p><a href="index.html">← Back to matrix</a></p>
{stale_note}
<h2>Documents archived</h2>
<ul class="coverage">{docs}</ul>
<h2>Extracted terms</h2>
<nav class="pdim-toc" aria-label="Jump to a term">{"".join(toc)}</nav>
{"".join(rows)}
<h2>Change history</h2>
{change_html}
<p class="genline">Extracted {esc(pmeta.get("extracted_at","")[:16].replace("T"," "))} UTC with {esc(pmeta.get("model",""))}.</p>
"""


def _change_item(c: dict) -> str:
    dims = c.get("dimensions", [])
    chips = ("".join(f'<span class="chip">{esc(d["label"])}</span>' for d in dims))
    chips = f'<div class="chips">{chips}</div>' if chips else ""

    # The AI summary is the primary readable content.
    if c.get("ai_explanation"):
        summary = (f'<p class="csummary">{esc(c["ai_explanation"])}</p>{chips}'
                   '<p class="ai-verify">AI-generated description; verify against the source '
                   'before relying on it.</p>')
    elif c.get("note"):
        summary = f'<p class="csummary muted-note">{esc(c["note"])}</p>'
    else:
        summary = ""

    # A collapsed lawyer-style redline (inline, in reading order) from the change
    # blocks: deletions struck through, insertions underlined. No side-by-side hunks.
    rl = "".join(
        (f'<del>{esc(b["old"])}</del> ' if b.get("old") else "")
        + (f'<ins>{esc(b["new"])}</ins> ' if b.get("new") else "")
        for b in c.get("blocks", [])
    ).strip()
    redline = (f'<details class="redline"><summary>View redline</summary>'
               f'<div class="rl">{rl}</div></details>') if rl else ""

    meta = f'<a class="csource" href="{esc(c["url"])}" target="_blank" rel="noopener">source</a>'
    dim_keys = " ".join(d["key"] for d in dims)
    substantive = c.get("substantive", True)
    cosmetic_tag = "" if substantive else '<span class="badge muted cosmetic-tag">cosmetic</span>'
    return f"""
<article class="change" data-provider="{esc(c["provider"])}" data-pname="{esc(c["provider_name"])}"
  data-date="{esc(c["detected_at"][:10])}" data-dims="{esc(dim_keys)}" data-substantive="{'1' if substantive else '0'}">
  <div class="chead"><strong>{esc(c["provider_name"])}</strong>: {esc(c["document"])}
    <span class="tag">{esc(c["doc_type"])}</span>{cosmetic_tag}
    <span class="cdate">{esc(c["detected_at"][:10])}</span></div>
  {summary}
  <div class="cfoot">{meta}{redline}</div>
</article>"""


def render_changes(dataset: dict) -> str:
    log = dataset.get("change_log", [])
    if not log:
        return _mark_state("All quiet. Still watching.")

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
    <label class="cf-cosmetic"><input type="checkbox" id="cf-cosmetic"> Show cosmetic changes</label>
    <button type="button" id="cf-clear" class="btn ghost">Clear filters</button>
  </div>
  <div class="cf-facets">
    <details class="pill"><summary>Filter providers</summary><div class="checks">{prov_checks}</div></details>
    <details class="pill"><summary>Filter provisions</summary><div class="checks">{prv_checks}</div></details>
  </div>
</div>"""
    items = "".join(_change_item(c) for c in log)
    return f"""{controls}
<div class="changes" id="cf-list">{items}</div>
<div id="cf-empty" hidden>{_mark_state("All quiet. Still watching.")}</div>"""


def render_site(dataset: dict, out_dir: Path = SITE_DIR) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    n = len(dataset["providers"])
    pages = {
        "index.html": ("Comparison matrix", render_matrix(dataset), "index",
                        f"An AI's side-by-side reading of the public terms of cloud infrastructure providers and AI model families ({n} entries). Every value carries a verbatim quote and a source link so you can verify it."),
        "changes.html": ("Change feed", render_changes(dataset), "changes",
                          "Detected changes to tracked documents, newest first."),
        "methodology.html": ("Methodology", render_methodology(dataset), "methodology",
                             "How the observatory archives, detects, and classifies published terms."),
        "about.html": ("About & coverage", render_about(dataset), "about", ""),
    }
    for fname, (title, body, active, subtitle) in pages.items():
        is_home = fname == "index.html"
        (out_dir / fname).write_text(
            _shell(title, body, active, subtitle, hide_title=is_home, home=is_home),
            encoding="utf-8")
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

    # 404 page (GitHub Pages serves /404.html for unknown paths).
    (out_dir / "404.html").write_text(
        _shell("Not found",
               _mark_state("Nothing observed here.", "index.html", "Back to the matrix"),
               active="", hide_title=True),
        encoding="utf-8")
    written.append(out_dir / "404.html")

    # Self-hosted fonts (same-origin; preserves the zero-third-party-request
    # property). Copied from assets/fonts into site/fonts, referenced by @font-face.
    import shutil

    font_src = Path("assets/fonts")
    if font_src.is_dir():
        font_out = out_dir / "fonts"
        font_out.mkdir(parents=True, exist_ok=True)
        for f in font_src.glob("*.woff2"):
            shutil.copy2(f, font_out / f.name)
            written.append(font_out / f.name)

    # Custom domain marker for GitHub Pages.
    if CUSTOM_DOMAIN:
        (out_dir / "CNAME").write_text(CUSTOM_DOMAIN + "\n", encoding="utf-8")
        written.append(out_dir / "CNAME")

    # Downloadable Excel workbooks: the full workbook (Export overflow) plus one
    # per section (scoped download in each section header).
    from .export import write_segment_workbook, write_workbook

    written.append(write_workbook(dataset, out_dir / EXPORT_XLSX))
    # One per-section workbook per view, so the .xlsx a reader downloads matches
    # the rows they are looking at.
    for group in EXPORT_XLSX_SEG:
        for view, _label, _groups in VIEWS:
            written.append(write_segment_workbook(
                dataset, group, EXPORT_XLSX_SEG_TITLE[group],
                out_dir / seg_xlsx_name(group, view), view))
    return written


_CSS = """
@font-face{font-family:"Space Grotesk";font-style:normal;font-weight:300 700;font-display:swap;
src:url("fonts/SpaceGrotesk.woff2") format("woff2")}
@font-face{font-family:"Baloo 2";font-style:normal;font-weight:800;font-display:swap;
src:url("fonts/Baloo2-800.woff2") format("woff2")}
:root{
/* Type */
--display:"Space Grotesk",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
--wordmark:"Baloo 2","Space Grotesk",-apple-system,sans-serif;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
/* Warm editorial palette — cream paper, warm ink, hairlines. Accents (tomato /
   marigold / cobalt) appear only in small doses: badges, pills, links, spot art. */
--bg:#faf6ef;--panel:#f4eee2;--panel-2:#ece3d3;--ink:#14120f;--muted:#6b6357;--faint:#78705d;
--line:#e5dfd2;--line-2:#d8d0bf;
/* --faint darkened to #78705d so small labels clear WCAG AA (4.5:1) on cream. */
--tomato:#e8502e;--marigold:#f5b72e;--cobalt:#2e5be8;
--accent:#2e5be8;--accent-2:#2e5be8;--accent-soft:#e7ecfc;
--high:#2e7d46;--medium:#c67d18;--low:#9a9080;
--disc-bg:#f7eee2;--disc-line:#ead9c0;--disc-fg:#7a4a22;
--old-bg:#fbe9e3;--old-fg:#9a2f1a;--new-bg:#e9f3ec;--new-fg:#2e7d46;
--shadow:none;
/* Structure — hairline borders and flat surfaces, no shadows or gradients. */
--radius:14px;--radius-sm:9px;--radius-pill:999px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;color:var(--ink);background:var(--bg);font-family:var(--sans);
font-size:15.5px;line-height:1.62;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1220px;margin:0 auto;padding:0 24px}
a{color:var(--accent-2);text-decoration:none}
a:hover{text-decoration:underline}

/* Header */
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.site-head{border-bottom:1px solid var(--line);background:var(--bg)}
.site-head .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:70px}
/* O.bservatory wordmark lockup */
.brand{display:flex;flex-direction:column;align-items:flex-start;gap:1px}
.brand:hover{text-decoration:none}
.wm-eyebrow{font-family:var(--display);color:var(--faint);font-size:10.5px;font-weight:600;
letter-spacing:.17em;text-transform:uppercase;line-height:1}
.wm-word{display:flex;align-items:flex-end;line-height:.85;color:var(--ink);font-size:31px}
.wm-o{width:1.3em;height:1.3em;flex:0 0 auto;margin-bottom:-.18em;margin-right:-.14em}
.wm-word .wm-o path{fill:var(--ink)}
.wm-txt{font-family:var(--wordmark);font-weight:800;letter-spacing:-.005em}
.nav{display:flex;gap:26px}
.nav a{color:var(--muted);font-family:var(--display);font-weight:600;font-size:11px;text-transform:uppercase;
letter-spacing:.12em;padding:4px 0;border-bottom:2px solid transparent}
.nav a.active{color:var(--ink);border-bottom-color:var(--ink)}
.nav a:hover{color:var(--ink);text-decoration:none}

/* Editorial deck line (replaces the boxed disclaimer). */
.deck{border-bottom:1px solid var(--line)}
.deck .wrap{padding:9px 24px}
.deck .wrap{font-family:Georgia,"Iowan Old Style","Times New Roman",serif;font-style:italic;
color:var(--muted);font-size:13.5px}
.deck a{color:inherit;text-decoration:underline;text-decoration-color:var(--line-2)}
.deck a:hover{color:var(--ink)}
.deck-short{display:none}
@media(max-width:640px){.deck-full{display:none}.deck-short{display:inline}}

/* Interior compact masthead: borderless, at most one hairline (under the deck). */
.is-interior .site-head{border-bottom:0}

/* Homepage centered hero (Roamie-style) */
.home-top{display:flex;justify-content:center;padding:24px 24px 0}
.home-top .nav{gap:30px}
.hero{padding:40px 24px 26px;text-align:center}
.hero-in{max-width:1040px;margin:0 auto}
.hero-wm{display:inline-flex;flex-direction:column;align-items:center}
.hero-wm .wm-eyebrow{font-size:clamp(11px,1.4vw,15px);letter-spacing:.24em;margin-bottom:8px}
.hero-wm .wm-word{font-size:clamp(52px,11vw,116px);justify-content:center;line-height:.9}
.hero-deck{margin:20px auto 0;max-width:620px;font-family:Georgia,"Iowan Old Style","Times New Roman",serif;
font-style:italic;color:var(--muted);font-size:clamp(14px,1.5vw,17px)}
.hero-deck a{color:inherit}
.hero-deck a:hover{color:var(--ink);text-decoration:none}

/* The chooser: the biggest interactive elements on the page. */
.chooser{display:flex;flex-direction:column;align-items:center;gap:12px;margin:6px 0 22px}
.chooser-main{display:flex;flex-wrap:wrap;justify-content:center;gap:12px}
.chooser-sub{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.chooser-sub[hidden]{display:none}
.cpill{font-family:var(--display);font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;
padding:15px 30px;border-radius:var(--radius-pill);border:1.5px solid var(--ink);background:transparent;
color:var(--ink);cursor:pointer;transition:background .12s}
.cpill:hover{background:var(--panel)}
.cpill.selected{background:var(--tomato);border-color:var(--tomato);color:var(--ink)}
.spill{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.09em;
padding:8px 16px;border-radius:var(--radius-pill);border:1px solid var(--line-2);background:transparent;
color:var(--muted);cursor:pointer}
.spill:hover{background:var(--panel);color:var(--ink)}
.spill.selected{background:var(--tomato);border-color:var(--tomato);color:var(--ink)}

/* The view switcher (which TERMS to show). Deliberately a different selected
   treatment from the chooser's tomato (which PROVIDERS to show), so the two
   stacked control rows never read as the same axis. */
.viewbar{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:0 0 18px;
padding-bottom:16px;border-bottom:1px solid var(--line)}
.vpill{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.09em;
padding:9px 18px;border-radius:var(--radius-pill);border:1px solid var(--line-2);background:transparent;
color:var(--muted);cursor:pointer;transition:background .12s,color .12s}
.vpill:hover{background:var(--panel);color:var(--ink)}
.vpill.selected{background:var(--ink);border-color:var(--ink);color:var(--bg)}

/* Per-group "show all N" expander row inside the matrix. */
.matrix tr.exprow td.expcell{position:sticky;left:0;background:var(--bg);border:0;
border-bottom:1px solid var(--line);padding:7px 12px}
.expbtn{font-family:var(--display);font-size:10.5px;font-weight:600;text-transform:uppercase;
letter-spacing:.08em;color:var(--muted);background:transparent;border:0;cursor:pointer;padding:3px 0}
.expbtn:hover{color:var(--ink);text-decoration:underline}
.pill>summary:hover{background:var(--panel)}
.pill-active{background:var(--tomato)!important;border-color:var(--tomato)!important;color:var(--ink)!important}

/* Compare mode: pick 2-3 providers, dimensions as stacked cards */
.cmp-pick{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 22px}
.cmp-pick-lbl{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.09em;color:var(--faint)}
.cmp-pick-pills{display:flex;flex-wrap:wrap;gap:7px}
.cmp-pp{font-family:var(--display);font-size:12px;font-weight:600;padding:6px 13px;border-radius:var(--radius-pill);
border:1px solid var(--line-2);background:var(--bg);color:var(--muted);cursor:pointer}
.cmp-pp:hover{color:var(--ink);border-color:var(--ink)}
.cmp-pp.selected{background:var(--tomato);border-color:var(--tomato);color:var(--ink)}
.cmp-dim{margin:0 0 24px}
.cmp-dim h4{font-family:var(--display);font-size:13.5px;font-weight:700;margin:0 0 10px;color:var(--ink);
padding-bottom:6px;border-bottom:1px solid var(--line)}
.cmp-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.cmp-card{border:1px solid var(--line);border-radius:var(--radius);padding:13px 15px;background:var(--bg)}
.cmp-card-prov{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-bottom:9px}
.cmp-card .cell-head{align-items:flex-start}
.cmp-card.cmp-na .na-cross-lbl{font-size:13px}
/* Mark used muted on empty states / 404, with a serif italic caption. */
.mark-state{display:flex;flex-direction:column;align-items:center;gap:16px;padding:56px 0 24px;text-align:center}
.mark-state svg{width:120px;height:120px;opacity:.4}
.mark-state p{margin:0;font-family:Georgia,"Iowan Old Style","Times New Roman",serif;font-style:italic;color:var(--muted);font-size:17px}
.ms-link{margin-top:2px!important}
.ms-link a{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.ms-link a:hover{color:var(--ink);text-decoration:none}

/* About page: accordion FAQ */
.faq-list{max-width:760px;border-top:1px solid var(--line)}
.faq{border-bottom:1px solid var(--line)}
.faq>summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;
gap:18px;padding:18px 2px;font-family:var(--display);font-size:17px;font-weight:600;color:var(--ink)}
.faq>summary::-webkit-details-marker{display:none}
.faq>summary:hover{color:var(--ink)}
.faq-ind{width:14px;height:14px;position:relative;flex:0 0 auto}
.faq-ind::before,.faq-ind::after{content:"";position:absolute;background:var(--ink);border-radius:1px}
.faq-ind::before{left:0;top:6px;width:14px;height:2px}
.faq-ind::after{left:6px;top:0;width:2px;height:14px;transition:transform .15s}
.faq[open] .faq-ind::after{transform:scaleY(0)}
.faq-a{padding:0 2px 20px;color:var(--muted);font-size:15px;line-height:1.65;max-width:70ch}
.faq-a p{margin:0}
.faq-a a{color:var(--accent)}
.faq-a em{font-family:Georgia,"Iowan Old Style","Times New Roman",serif;font-style:italic;color:var(--ink)}
/* Big-number stat callouts (homepage). Hairline cards, huge figure, tiny label. */
.stats{display:flex;flex-wrap:wrap;gap:14px;margin:2px 0 22px}
.stat{flex:1 1 150px;border:1px solid var(--line);border-radius:var(--radius);padding:15px 18px;background:var(--bg)}
.stat-num{display:block;font-family:var(--display);font-weight:700;font-size:40px;line-height:1;letter-spacing:-.02em;color:var(--ink)}
.stat-lbl{display:block;margin-top:9px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.09em;color:var(--faint)}
.disc-icon{flex:0 0 auto;width:17px;height:17px;border-radius:50%;background:var(--disc-fg);color:var(--disc-bg);
font-style:italic;font-weight:700;font-family:var(--display);font-size:12px;line-height:17px;text-align:center;margin-top:1px}

/* Headings */
main.wrap{padding-top:30px;padding-bottom:72px}
/* Page title sits subordinate to the masthead brand wordmark (B1). */
h1{font-family:var(--display);font-weight:600;font-size:21px;letter-spacing:-.005em;margin:0 0 6px}
.subtitle{color:var(--muted);margin:0 0 26px;font-size:16px;max-width:70ch}
h2{font-family:var(--display);font-weight:600;font-size:21px;margin:34px 0 12px}
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
.matrix th.corner{left:0;z-index:5;font-family:var(--display);font-weight:600}
.matrix th.dim-col{position:sticky;left:0;z-index:2;background:var(--panel);min-width:186px;max-width:206px;
font-size:13.5px;font-weight:600;color:var(--ink)}
.matrix th.prov-col a{color:var(--accent-2);font-weight:700}
.matrix tbody tr:hover td.cell{background:var(--accent-soft)}
.matrix td.cell{min-width:236px;max-width:290px;background:var(--bg);transition:background .12s}
.matrix tr.grouprow th.groupcell{position:sticky;left:0;background:var(--panel-2);color:var(--muted);
font-family:var(--display);font-weight:700;font-size:12.5px;text-transform:uppercase;letter-spacing:.09em;
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
.pdim-toc{display:flex;flex-wrap:wrap;gap:6px 8px;margin:0 0 22px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.pdim-toc a{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;
color:var(--muted);padding:4px 10px;border:1px solid var(--line-2);border-radius:var(--radius-pill)}
.pdim-toc a:hover{color:var(--ink);border-color:var(--ink);text-decoration:none}
.pdim{border:1px solid var(--line-2);border-radius:12px;padding:16px 18px;margin:12px 0;background:var(--bg);box-shadow:var(--shadow);scroll-margin-top:20px}
.pdim h4{margin:0 0 9px;font-size:16px;color:var(--ink);text-transform:none;letter-spacing:0;font-weight:700;
font-family:var(--sans);display:flex;align-items:center;gap:9px}
/* Dimension-group heading on a provider page, and its TOC separator. */
.pgrp{margin:26px 0 10px;font-family:var(--display);font-size:11px;font-weight:600;
text-transform:uppercase;letter-spacing:.12em;color:var(--faint);scroll-margin-top:20px}
.pdim-toc-h{font-family:var(--display);font-size:10px;font-weight:600;text-transform:uppercase;
letter-spacing:.1em;color:var(--faint);align-self:center;padding:4px 2px 4px 8px}
.pdim-toc-h:first-child{padding-left:0}
.pval{margin:0 0 8px;max-width:none}
.cite{color:var(--muted);font-style:italic}
.ovnote{margin-top:7px;font-size:12.5px;color:var(--accent-2)}
.empty{color:var(--muted);background:var(--panel);border:1px solid var(--line-2);border-radius:12px;padding:20px}

/* Change feed */
.changes{display:flex;flex-direction:column;gap:14px}
.change{border:1px solid var(--line-2);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.chead{display:flex;gap:9px;align-items:center;flex-wrap:wrap;font-family:var(--display)}
.cdate{margin-left:auto;color:var(--faint);font-size:13px;font-family:var(--sans)}
/* Change entry: AI summary is primary; a collapsed lawyer-style redline below. */
.csummary{margin:10px 0 4px;font-size:15px;line-height:1.55;color:var(--ink);max-width:80ch}
.muted-note{color:var(--muted);font-style:italic}
.ai-verify{font-size:11.5px;font-style:italic;color:var(--muted);margin:6px 0 0}
.cfoot{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin-top:10px}
.csource{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.csource:hover{color:var(--ink);text-decoration:none}
.redline>summary{list-style:none;cursor:pointer;font-family:var(--display);font-size:11px;font-weight:600;
text-transform:uppercase;letter-spacing:.08em;color:var(--accent)}
.redline>summary::-webkit-details-marker{display:none}
.rl{margin-top:9px;padding:12px 14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;
line-height:2;font-size:13.5px;color:var(--ink)}
.rl del{text-decoration:line-through;text-decoration-color:#bd7862;color:#a85c46}
.rl ins{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:2px;color:var(--ink)}
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
.btn{display:inline-flex;align-items:center;gap:7px;background:var(--ink);color:var(--bg);
border:1px solid var(--ink);border-radius:var(--radius-pill);padding:9px 18px;font-size:13px;font-weight:600;
letter-spacing:.01em;cursor:pointer;text-decoration:none;font-family:var(--display)}
.btn:hover{background:#2a2620;border-color:#2a2620;text-decoration:none}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line-2)}
.btn.ghost:hover{background:var(--panel)}
.updated{margin-left:auto;color:var(--faint);font-size:12.5px}
.freshness{margin:0 0 14px;font-size:14px;color:var(--muted);background:var(--panel);
border:1px solid var(--line-2);border-radius:9px;padding:9px 13px;display:inline-block}
.freshness strong{color:var(--ink)}

/* Section nav (sticky, scroll-spy) */
.secnav{position:sticky;top:0;z-index:15;display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;
background:var(--bg);border-bottom:1px solid var(--line-2);padding:10px 0;margin:0 0 16px}
.secnav a{color:var(--muted);text-decoration:none;font-weight:600;font-size:14px;padding:3px 2px;border-bottom:2px solid transparent}
.secnav a:hover{color:var(--ink)}
.secnav a.active{color:var(--accent-2);border-bottom-color:var(--accent)}
.sn-model{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px}
.sn-subs{display:flex;gap:12px}
.sn-sub{font-size:12.5px;font-weight:600;color:var(--faint)}
.secnav .cnt{display:inline-block;background:var(--panel-2);border-radius:20px;padding:0 7px;font-size:11px;color:var(--muted);margin-left:3px}

/* Controls */
.controls{margin:0 0 14px;display:flex;flex-direction:column;gap:10px}
.ctl-row{display:flex;flex-wrap:wrap;gap:12px 18px;align-items:center}
.ctl-row label{font-size:13px;color:var(--muted);display:flex;gap:6px;align-items:center}
.ctl-row select{font:inherit;font-size:13px;padding:6px 9px;border:1px solid var(--line-2);border-radius:8px;background:var(--bg);color:var(--ink)}
.facets{display:flex;flex-wrap:wrap;gap:10px}
.facets details{border:1px solid var(--line-2);border-radius:10px;padding:9px 13px;background:var(--panel)}
.facets summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--ink)}

/* Sections */
.msec{margin:0 0 34px;scroll-margin-top:64px}
.msub{margin:16px 0 0;scroll-margin-top:64px}
.sec-h{font-family:var(--display);font-weight:600;font-size:22px;margin:0 0 4px;display:flex;align-items:center;gap:9px}
.sub-h{font-size:13px;margin:18px 0 8px;color:var(--accent-2);text-transform:uppercase;letter-spacing:.07em;display:flex;align-items:center;gap:8px}
.sec-note{color:var(--muted);font-size:13.5px;margin:0 0 12px;max-width:78ch}
.col-sub{display:block;margin-top:2px;font-weight:400;font-size:11px;color:var(--muted);letter-spacing:0;text-transform:none}

/* --- Revised toolbar + per-section header controls --- */
.toolbar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;margin:0 0 24px}
.tb-filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{position:relative}
.pill>summary,.pill-btn{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:6px;
font-family:var(--display);font-size:12px;font-weight:600;letter-spacing:.02em;color:var(--ink);
background:var(--bg);border:1px solid var(--line-2);border-radius:var(--radius-pill);padding:7px 15px}
.pill>summary::-webkit-details-marker{display:none}
.pill>summary::after{content:"";width:5px;height:5px;border-right:1.5px solid var(--faint);
border-bottom:1.5px solid var(--faint);transform:rotate(45deg);margin:-3px 0 0 2px}
.pill[open]>summary{background:var(--panel);border-color:var(--ink)}
.pill .checks,.export-menu .menu{position:absolute;top:calc(100% + 6px);left:0;z-index:20;min-width:184px;
background:var(--bg);border:1px solid var(--line-2);border-radius:12px;padding:11px 13px;
display:flex;flex-direction:column;gap:8px}
.export-menu{margin-left:auto}
.export-menu .menu{left:auto;right:0}
.export-menu .menu a,.export-menu .menu button{font:inherit;font-family:var(--sans);font-size:13px;color:var(--ink);
background:none;border:0;text-align:left;cursor:pointer;padding:2px 0;text-decoration:none}
.export-menu .menu a:hover,.export-menu .menu button:hover{color:var(--accent)}
.sec-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:10px 16px;
margin:0 0 14px;padding-bottom:9px;border-bottom:1px solid var(--line)}
.sec-h{font-family:var(--display);font-weight:700;font-size:20px;margin:0;display:flex;align-items:baseline;gap:10px}
.sec-cnt{font-family:var(--display);font-size:12px;font-weight:600;color:#7c5510;
background:#fbeecb;border-radius:var(--radius-pill);padding:1px 9px}
.sec-ctl{display:flex;flex-wrap:wrap;align-items:center;gap:14px}
.sec-fresh{font-family:var(--display);font-size:10.5px;font-weight:600;text-transform:uppercase;
letter-spacing:.09em;color:var(--faint)}
.sec-sort{font-size:12px;color:var(--muted);display:flex;gap:6px;align-items:center}
.sec-sort select{font:inherit;font-size:12px;padding:4px 8px;border:1px solid var(--line-2);
border-radius:8px;background:var(--bg);color:var(--ink)}
.sec-exports{display:flex;gap:6px}
.sec-x{font-family:var(--display);font-size:11px;font-weight:600;color:var(--muted);background:var(--bg);
border:1px solid var(--line-2);border-radius:var(--radius-pill);padding:3px 11px;cursor:pointer;text-decoration:none}
.sec-x:hover{color:var(--ink);border-color:var(--ink);text-decoration:none}
.mgroup{margin:8px 0 0}
.mgroup-h{font-family:var(--display);font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:.1em;
color:var(--faint);margin:0 0 16px;padding-bottom:0}

/* Unverified / status distinction */
/* Four honest status states (Issue 2). Warning reserved for quote_unverified;
   absence states get neutral, muted treatment. */
.dot.warn,.dot.unverified{background:transparent;border:1.5px solid var(--tomato)}
.dot.ok{background:var(--high)}
.dot.absent{background:var(--line-2)}
.dot.na{background:transparent;border:1.5px dotted var(--faint)}
.cell.unverified .toggle{color:var(--muted);font-style:italic}
.cell.absent .toggle{color:var(--faint)}
.cell.na-cross{background:repeating-linear-gradient(45deg,transparent,transparent 6px,var(--panel) 6px,var(--panel) 7px)}
.na-cross-lbl{color:var(--faint);font-size:12px;font-style:italic}
/* Text-first status badges: subtle tint + colored text, pill-shaped. */
.badge.ok,.badge.warn,.badge.muted,.badge.stale{border-radius:var(--radius-pill);
padding:1px 9px;font-size:11px;font-weight:600;font-family:var(--display);letter-spacing:.01em;border:1px solid}
.badge.ok{background:#e9f3ec;color:#1f6b38;border-color:#c3e0cc}
.badge.warn{background:#fbe9e3;color:#b23a1c;border-color:#f2c3b6}
.badge.muted{background:var(--panel);color:var(--muted);border-color:var(--line-2)}
.badge.stale{background:#fbf0dc;color:var(--medium);border-color:#ecd6a6}
.src.wayback{color:var(--muted)}
.wb-note{font-size:11.5px;font-style:italic;color:var(--faint);margin:3px 0}
.col-stale{display:block;margin-top:2px;font-size:10.5px;font-weight:700;color:var(--medium);letter-spacing:0;text-transform:none}
.stale-note{background:var(--disc-bg);border:1px solid var(--disc-line);color:var(--disc-fg);
border-radius:9px;padding:10px 13px;font-size:13.5px;margin:0 0 16px}

@media(max-width:680px){
  .secnav{flex-wrap:nowrap;overflow-x:auto;gap:14px}
  .secnav a{white-space:nowrap}
  .sn-model{flex-wrap:nowrap}
}

/* Print / Save as PDF: hide chrome, expand full values, fit to landscape paper */
@media print{
@page{size:landscape;margin:12mm}
.site-head,.filters,.actions,.toolbar,.deck,.site-foot,.genline,.sec-ctl{display:none!important}
/* Controls, not content: the printed page keeps whichever rows the view is showing. */
.viewbar,.chooser,.matrix tr.exprow{display:none!important}
body[data-print-sec] .msec:not(.print-me){display:none!important}
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
h1{font-size:20px}.matrix td.cell{min-width:210px}.table-scroll{max-height:74vh}
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
// --- Front page: facet filters (combinable), column sort, flat view, sticky nav ---
(function(){
  var PM = window.CTO_PROVIDERS || {};
  if(!document.getElementById('grouped-view')) return;
  var ids = Object.keys(PM);

  function checkedVals(cls){ return [].slice.call(document.querySelectorAll(cls)).filter(function(c){return c.checked;}).map(function(c){return c.value;}); }
  // A facet only narrows when the user has UNchecked some of its options.
  function narrowed(cls){ var all=document.querySelectorAll(cls), v=checkedVals(cls); return v.length<all.length ? v : null; }

  function visible(){
    var seg=narrowed('.f-seg'), op=narrowed('.f-open'), par=narrowed('.f-parent'), lic=narrowed('.f-lic');
    var vis={};
    ids.forEach(function(id){
      var a=PM[id], ok=true;
      if(seg && seg.indexOf(a.seg)<0) ok=false;
      if(op  && op.indexOf(a.open)<0) ok=false;   // empty openness -> hidden when openness is narrowed
      if(par && par.indexOf(a.parent)<0) ok=false;
      if(lic && lic.indexOf(a.lic)<0) ok=false;
      vis[id]=ok;
    });
    return vis;
  }

  // Sorting is per-section now: each section's select reorders only its table.
  function sortTable(tbl, mode){
    var head=tbl.querySelector('thead tr'); if(!head) return;
    var cols=[].slice.call(head.querySelectorAll('.prov-col')).sort(function(a,b){
      var A=PM[a.dataset.provider]||{}, B=PM[b.dataset.provider]||{};
      if(mode==='updated') return (B.upd||'').localeCompare(A.upd||'');
      return (A.name||'').localeCompare(B.name||'');
    });
    cols.forEach(function(c){head.appendChild(c);});
    var order=cols.map(function(c){return c.dataset.provider;});
    tbl.querySelectorAll('tbody tr[data-dim]').forEach(function(tr){
      order.forEach(function(pid){ var td=tr.querySelector('td.cell[data-provider="'+pid+'"]'); if(td) tr.appendChild(td); });
    });
  }
  function sortSection(sel){ var tbl=document.getElementById(sel.dataset.target); if(tbl) sortTable(tbl, sel.value); }

  function apply(){
    var vis=visible();
    document.querySelectorAll('.prov-col,.cell').forEach(function(el){ el.style.display = vis[el.dataset.provider] ? '' : 'none'; });
    function cnt(pred){ return ids.filter(function(id){return vis[id] && pred(PM[id]);}).length; }
    var c={cloud:cnt(function(a){return a.seg==='hyperscaler'||a.seg==='neocloud';}),
           closed:cnt(function(a){return a.seg==='model_provider'&&a.open==='closed_api';}),
           open:cnt(function(a){return a.seg==='model_provider'&&a.open==='open_weight';})};
    c.model=c.closed+c.open;
    document.querySelectorAll('[data-cnt]').forEach(function(el){ if(c[el.dataset.cnt]!=null) el.textContent=c[el.dataset.cnt]; });
  }

  // Print one section only: isolate it for the print stylesheet, then restore.
  function printSection(sec){
    var el=document.getElementById(sec); if(!el) return;
    el.classList.add('print-me'); document.body.setAttribute('data-print-sec', sec);
    window.addEventListener('afterprint', function h(){
      el.classList.remove('print-me'); document.body.removeAttribute('data-print-sec');
      window.removeEventListener('afterprint', h);
    });
    window.print();
  }

  document.addEventListener('change',function(e){
    if(e.target.matches('.f-seg,.f-open,.f-parent,.f-lic')) apply();
    if(e.target.matches('.sec-sort-sel')) sortSection(e.target);
  });
  document.addEventListener('click',function(e){
    var pb=e.target.closest('[data-print-sec]'); if(pb){ e.preventDefault(); printSection(pb.dataset.printSec); }
  });

  // The chooser owns which section(s) render (segment + openness selection).
  function setSec(id, on){ var el=document.getElementById(id); if(el) el.style.display = on ? '' : 'none'; }
  function applyChooser(choose, sub){
    var s={cloud:false, closed:false, open:false};
    if(choose==='all'){ s.cloud=s.closed=s.open=true; }
    else if(choose==='cloud'){ s.cloud=true; }
    else if(choose==='model'){
      if(sub==='closed'){ s.closed=true; }
      else if(sub==='open'){ s.open=true; }
      else { s.closed=s.open=true; }
    }
    setSec('cloud-infrastructure', s.cloud); setSec('closed-api', s.closed); setSec('open-weight', s.open);
    var subEl=document.getElementById('chooser-sub'); if(subEl) subEl.hidden = (choose!=='model');
  }
  var chooser=document.getElementById('chooser');
  if(chooser){
    var choose='all', sub='all';
    chooser.addEventListener('click',function(e){
      var m=e.target.closest('[data-choose]'), sp=e.target.closest('[data-sub]');
      if(m){ choose=m.dataset.choose;
        chooser.querySelectorAll('.cpill').forEach(function(b){ b.classList.toggle('selected', b===m); });
        if(choose!=='model'){ sub='all'; chooser.querySelectorAll('.spill').forEach(function(b){ b.classList.toggle('selected', b.dataset.sub==='all'); }); }
        applyChooser(choose, sub);
      } else if(sp){ sub=sp.dataset.sub;
        chooser.querySelectorAll('.spill').forEach(function(b){ b.classList.toggle('selected', b===sp); });
        applyChooser(choose, sub);
      }
    });
  }

  // The view switcher owns which dimension ROWS render (the chooser owns which
  // provider sections render). "key" shows the curated subset of every group with
  // a per-group expander; every other view shows its group(s) in full.
  var viewbar=document.getElementById('viewbar');
  if(viewbar){
    var VIEW_GROUPS=window.CTO_VIEW_GROUPS||{}, view='key', expanded={};
    function applyView(){
      var groups=VIEW_GROUPS[view]||null;  // null => "key": every group, curated rows
      ['tbl-cloud','tbl-closed','tbl-open'].forEach(function(id){
        var t=document.getElementById(id); if(!t) return;
        t.querySelectorAll('tbody tr').forEach(function(tr){
          var g=tr.dataset.group||'', inView=groups ? groups.indexOf(g)>=0 : true, show;
          if(tr.classList.contains('exprow')){
            show = inView && !groups && !expanded[id+'||'+g];
          } else if(tr.classList.contains('grouprow')){
            show = inView;
          } else {
            show = inView && (groups || tr.dataset.key==='1' || expanded[id+'||'+g]);
          }
          tr.style.display = show ? '' : 'none';
        });
      });
      viewbar.querySelectorAll('.vpill').forEach(function(b){ b.classList.toggle('selected', b.dataset.view===view); });
      // Per-section .xlsx downloads follow the active view.
      document.querySelectorAll('a.sec-x[data-xlsx]').forEach(function(a){
        var map; try{ map=JSON.parse(a.dataset.xlsx); }catch(err){ return; }
        if(map[view]) a.setAttribute('href', map[view]);
      });
      // Reflect the view in the URL so a view is linkable and survives reload.
      try{
        var u=new URL(window.location.href);
        if(view==='key') u.searchParams.delete('view'); else u.searchParams.set('view', view);
        history.replaceState(null,'',u);
      }catch(err){}
    }
    viewbar.addEventListener('click',function(e){
      var b=e.target.closest('[data-view]'); if(!b) return;
      view=b.dataset.view; expanded={};   // a fresh view starts collapsed
      applyView();
    });
    document.addEventListener('click',function(e){
      var x=e.target.closest('[data-expand]'); if(!x) return;
      var t=x.closest('table'); if(!t) return;
      expanded[t.id+'||'+x.dataset.expand]=true;
      applyView();
    });
    try{
      var want=new URL(window.location.href).searchParams.get('view');
      if(want && (want==='key' || VIEW_GROUPS[want])) view=want;
    }catch(err){}
    applyView();
  }

  // Compare mode: pick 2-3 providers; dimensions render as stacked cards, reusing
  // the existing cells (so the detail toggle keeps working).
  var compareBtn=document.getElementById('compare-btn'), compareView=document.getElementById('compare-view');
  if(compareBtn && compareView){
    var chooserEl=document.getElementById('chooser'), groupedEl=document.getElementById('grouped-view');
    var cmpEmpty=document.getElementById('cmp-empty'), cmpOut=document.getElementById('cmp-out');
    var cesc=function(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;};
    var selected=[], cellMap=null;
    function buildMap(){ cellMap={}; ['tbl-cloud','tbl-closed','tbl-open'].forEach(function(id){
      var t=document.getElementById(id); if(!t) return;
      t.querySelectorAll('tbody td.cell').forEach(function(td){ if(td.dataset.provider) cellMap[td.dataset.provider+'||'+td.dataset.dim]=td; }); }); }
    function renderCompare(){
      if(selected.length<2){ cmpEmpty.hidden=false; cmpOut.innerHTML=''; return; }
      cmpEmpty.hidden=true; if(!cellMap) buildMap();
      var html='';
      (window.CTO_DIMS||[]).forEach(function(d){
        if(!selected.some(function(pid){return cellMap[pid+'||'+d.key];})) return; // all N/A -> skip
        var cards='';
        selected.forEach(function(pid){
          var pname=(PM[pid]||{}).name||pid, cell=cellMap[pid+'||'+d.key];
          cards += cell
            ? '<div class="cmp-card cell"><div class="cmp-card-prov">'+cesc(pname)+'</div>'+cell.innerHTML+'</div>'
            : '<div class="cmp-card cmp-na"><div class="cmp-card-prov">'+cesc(pname)+'</div><span class="na-cross-lbl">not applicable for this provider type</span></div>';
        });
        html += '<div class="cmp-dim"><h4>'+cesc(d.label)+'</h4><div class="cmp-cards">'+cards+'</div></div>';
      });
      cmpOut.innerHTML=html;
    }
    compareView.querySelector('.cmp-pick-pills').addEventListener('click',function(e){
      var b=e.target.closest('.cmp-pp'); if(!b) return;
      var pid=b.dataset.pid, i=selected.indexOf(pid);
      if(i>=0){ selected.splice(i,1); b.classList.remove('selected'); }
      else if(selected.length<3){ selected.push(pid); b.classList.add('selected'); }
      renderCompare();
    });
    compareBtn.addEventListener('click',function(){
      var on=compareView.hasAttribute('hidden');
      if(on){ compareView.removeAttribute('hidden'); } else { compareView.setAttribute('hidden',''); }
      if(chooserEl) chooserEl.style.display = on ? 'none' : '';
      if(groupedEl) groupedEl.style.display = on ? 'none' : '';
      compareBtn.classList.toggle('pill-active', on);
    });
  }

  // Do not auto-sort on load: the server-rendered order (curated for Cloud
  // Infrastructure) is the default; per-section sort is applied on demand.
  apply();
})();

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
    var showCosmetic=document.getElementById('cf-cosmetic').checked;
    var dimsNarrowed=dims.length<totalDim, visible=0;
    items.forEach(function(a){
      var show=true;
      if(!showCosmetic && a.dataset.substantive==='0') show=false;
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
    if(e.target.matches('.cf-prov,.cf-dim,#cf-sort,#cf-from,#cf-to,#cf-cosmetic')) apply();
  });
  document.getElementById('cf-clear').addEventListener('click',function(){
    document.querySelectorAll('.cf-prov,.cf-dim').forEach(function(c){c.checked=true;});
    document.getElementById('cf-from').value=''; document.getElementById('cf-to').value='';
    document.getElementById('cf-sort').value='date-desc'; apply();
  });
  apply();
})();
"""
