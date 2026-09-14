#!/usr/bin/env python3
"""Generate the static SAT Heritage website from the repository metadata.

Inputs: ``index.json``, every ``<set>/solvers.json`` and ``<set>/setup.json``,
and ``data/test-results.json`` (written by ``tools/collect_test_results.py``).
Output: a self-contained static site in ``site/`` (or ``--output``) with a
searchable catalogue and one page per solver image, in the spirit of the
model cards of model hubs.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

DOCKER_NS = "satex"
REPO_URL = "https://github.com/sat-heritage/docker-images"
COMPETITION_URL = {
    2022: "https://satcompetition.github.io/2022/",
    2023: "https://satcompetition.github.io/2023/",
    2024: "https://satcompetition.github.io/2024/",
    2025: "https://satcompetition.github.io/2025/",
    2026: "https://satcompetition.github.io/2026/",
}
BUILD_KIND_LABEL = {
    "starexec": "submitted starexec_build",
    "build-subdir": "submitted build/build.sh",
    "script": "submitted build script",
    "configure": "configure and make",
    "make": "make",
    "command": "explicit command",
    "auto": "auto-detected",
}
VERDICT_LABEL = {
    "verified": ("Verified", "ok"),
    "runs": ("Runs, checks failed", "warn"),
    "built": ("Compiles", "warn"),
    "source-available": ("Source available, build fails", "fail"),
    "source-unavailable": ("Source unavailable", "fail"),
    "unknown": ("Not run yet", "none"),
}
# ordinal ladder for the per-year chart, lowest rung first (validated 5-step blue ramp)
LADDER = ["source-unavailable", "source-available", "built", "runs", "verified"]
LADDER_LABEL = {"source-unavailable": "source unavailable", "source-available": "source available",
                "built": "compiles", "runs": "runs", "verified": "verified"}
STATUS_LABEL = {
    "ok": ("builds", "ok"),
    "unstable": ("unstable", "warn"),
    "fixme": ("not buildable", "fail"),
    "unknown": ("unknown", "none"),
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def load_json(path: Path):
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def family_of(entry: dict, setup: dict) -> str:
    call = str(entry.get("call", "")).lower()
    name = str(entry.get("name", "")).lower()
    for probe, family in [("kissat", "Kissat"), ("cadical", "CaDiCaL"), ("glucose", "Glucose"),
                          ("maple", "Maple"), ("minisat", "MiniSat"), ("mergesat", "MergeSat"),
                          ("lingeling", "Lingeling"), ("cryptominisat", "CryptoMiniSat"),
                          ("seqfrost", "SeqFROST"), ("slime", "SLIME"), ("isasat", "IsaSAT")]:
        if probe in call or probe in name:
            return family
    return "other"


def recipe_origin(block: dict, setup: dict) -> str:
    builder = block.get("builder", setup.get("builder", ""))
    if builder.startswith("generic/starexec"):
        kind = block.get("BUILD_KIND", "auto")
        if kind == "command" and "build.sh" in block.get("BUILD_COMMAND", ""):
            return "submitted build script"
        return BUILD_KIND_LABEL.get(kind, kind)
    if builder.startswith("generic/binary"):
        return "binary distribution"
    return f"builder {builder}"


def collect(repo: Path) -> list[dict]:
    index = load_json(repo / "index.json")
    results = {}
    results_file = repo / "data" / "test-results.json"
    if results_file.is_file():
        results = load_json(results_file).get("images", {})
    solvers = []
    for entry_set in index:
        set_dir = repo / str(entry_set)
        solvers_file = set_dir / "solvers.json"
        if not solvers_file.is_file():
            continue
        registry = load_json(solvers_file)
        setup = load_json(set_dir / "setup.json") if (set_dir / "setup.json").is_file() else {}
        for key, entry in registry.items():
            image = f"{key}:{entry_set}"
            block = dict(setup)
            block.update(setup.get(key, {}) if isinstance(setup.get(key), dict) else {})
            result = results.get(image, {})
            args_text = " ".join(map(str, entry.get("args", [])))
            checks = result.get("tests", {})
            capabilities = []
            if checks.get("sat-model", {}).get("status") == "ok":
                capabilities.append("SAT")
            if checks.get("unsat-result", {}).get("status") == "ok":
                capabilities.append("UNSAT")
            if checks.get("unsat-proof", {}).get("status") == "ok":
                capabilities.append("UNSAT+proof")
            elif "argsproof" in entry and not checks:
                capabilities.append("proof (declared)")
            if not checks and "argsproof" not in entry:
                capabilities.append("SAT/UNSAT (declared)")
            # "parallel" means the competition's parallel track, not a multi-threaded default
            if "parallel" in [t.lower() for t in entry.get("tracks", [])]:
                capabilities.append("parallel")
            if entry.get("gz"):
                capabilities.append("gzip input")
            solvers.append({
                "capabilities": capabilities,
                "image": image,
                "key": key,
                "set": str(entry_set),
                "name": entry.get("name", key),
                "version": entry.get("version", ""),
                "authors": entry.get("authors", ""),
                "status": entry.get("status", "unknown"),
                "status_detail": entry.get("status_detail", ""),
                "comment": entry.get("comment") or entry.get("comments", ""),
                "tracks": entry.get("tracks", []),
                "call": entry.get("call", ""),
                "args": entry.get("args", []),
                "proof": "argsproof" in entry,
                "gz": bool(entry.get("gz", False)),
                "family": family_of(entry, setup),
                "recipe": recipe_origin(block, setup),
                "builder": block.get("builder", ""),
                "builder_base": block.get("builder_base", block.get("base_from", "")),
                "apt_snapshot": block.get("APT_SNAPSHOT", ""),
                "build_command": block.get("BUILD_COMMAND", ""),
                "build_depends": block.get("BUILD_DEPENDS", ""),
                "rdepends": block.get("RDEPENDS", ""),
                "download_url": (block.get("download_url", "") or "").replace("{SOLVER_NAME}", entry.get("name", key)),
                "verdict": result.get("verdict", "unknown"),
                "tested": result.get("date", ""),
                "build_stages": result.get("build", {}),
                "checks": result.get("tests", {}),
            })
    return solvers


CSS = """
:root { --bg:#ffffff; --bg2:#f8f9fb; --card:#ffffff; --ink:#0b0b0b; --muted:#5e6572; --line:#e5e7eb; --ok:#1a7f37; --warn:#9a6700; --fail:#cf222e; --none:#8c959f; --accent:#0b57d0; --hf:#ffd21e; --hfdark:#f59e0b; --cap:#0550ae; --capbg:#e8f1ff; --series-1:#2a78d6; --series-2:#eda100; --grid:#e5e7eb; --l0:#86b6ef; --l1:#5598e7; --l2:#2a78d6; --l3:#1c5cab; --l4:#104281; --l-none:#d4d6da; }
@media (prefers-color-scheme: dark) { :root { --bg:#0b0f19; --bg2:#111827; --card:#161b26; --ink:#f3f4f6; --muted:#9aa3b2; --line:#2a3140; --ok:#3fb950; --warn:#d29922; --fail:#f85149; --none:#6e7681; --accent:#7ab4ff; --cap:#9ecbff; --capbg:#12305c; --series-1:#3987e5; --series-2:#c98500; --grid:#2a3140; --l0:#9ec5f4; --l1:#6da7ec; --l2:#3987e5; --l3:#256abf; --l4:#184f95; --l-none:#3a4150; } }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bg); }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; } a.card:hover { text-decoration:none; border-color:var(--accent); }
header { padding:16px 24px; border-bottom:1px solid var(--line); background:var(--card); display:flex; align-items:center; gap:18px; flex-wrap:wrap; }
header .logo { display:flex; align-items:center; gap:10px; font-weight:700; font-size:20px; } header .logo span.dot { width:26px; height:26px; border-radius:8px; background:var(--hf); display:inline-block; }
header nav a { margin-right:16px; color:var(--ink); font-weight:500; } header nav a.active { border-bottom:2px solid var(--hf); }
header p { margin:0; color:var(--muted); margin-left:auto; }
.hero { padding:36px 0 8px; } .hero h1 { font-size:34px; margin:0 0 6px; } .hero p { color:var(--muted); font-size:17px; margin:0 0 18px; max-width:760px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin:8px 0 22px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.stat .n { font-size:28px; font-weight:700; } .stat .l { color:var(--muted); font-size:13px; }
.two { display:grid; grid-template-columns:repeat(auto-fit, minmax(340px, 1fr)); gap:14px; }
.fig { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.fig h2 { margin:0 0 2px; font-size:16px; } .fig .sub { color:var(--muted); font-size:13px; margin-bottom:8px; }
.fig svg { width:100%; height:auto; display:block; } .fig text { fill:var(--ink); font-size:12px; } .fig text.muted { fill:var(--muted); } .fig line.grid { stroke:var(--grid); }
.legend2 { display:flex; gap:14px; font-size:13px; color:var(--muted); margin-top:6px; } .sw { display:inline-block; width:12px; height:12px; border-radius:3px; vertical-align:-1px; margin-right:5px; }
.facts { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; }
.fact { background:var(--bg2); border-radius:12px; padding:12px 14px; } .fact b { display:block; } .fact span { color:var(--muted); font-size:13px; }
.btn { display:inline-block; background:var(--hf); color:#0b0b0b; padding:10px 16px; border-radius:10px; font-weight:600; } .btn:hover { text-decoration:none; filter:brightness(.95); }
main { max-width:1200px; margin:0 auto; padding:20px 24px 60px; }
.toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:8px 0 18px; }
.toolbar input, .toolbar select { font:inherit; padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--ink); }
.toolbar input { flex:1 1 260px; } .count { color:var(--muted); margin-left:auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:14px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; display:flex; flex-direction:column; gap:6px; }
.card h3 { margin:0; font-size:16px; } .card .meta { color:var(--muted); font-size:13px; }
.tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
.tag { font-size:12px; padding:2px 8px; border-radius:999px; border:1px solid var(--line); color:var(--muted); background:transparent; }
.tag.id { border-style:dashed; }
.tag.cap { border-color:transparent; background:var(--capbg); color:var(--cap); }
.tagrow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
.tagrow .lbl { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); width:64px; }
.legend { color:var(--muted); font-size:13px; display:flex; gap:14px; flex-wrap:wrap; margin:-6px 0 14px; }
.badge { font-size:12px; padding:2px 8px; border-radius:999px; color:#fff; }
.badge.ok { background:var(--ok);} .badge.warn { background:var(--warn);} .badge.fail { background:var(--fail);} .badge.none { background:var(--none);}
.page h1 { margin-bottom:0; } .page .sub { color:var(--muted); margin-top:2px; }
.section { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:16px 0; }
.section h2 { margin:0 0 10px; font-size:17px; }
dl { display:grid; grid-template-columns:max-content 1fr; gap:6px 16px; margin:0; } dt { color:var(--muted); } dd { margin:0; word-break:break-word; }
pre { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:10px 12px; overflow-x:auto; font-size:13px; }
table { border-collapse:collapse; width:100%; font-size:14px; } td, th { text-align:left; padding:4px 8px; border-bottom:1px solid var(--line); }
.crumbs { color:var(--muted); font-size:14px; margin-bottom:8px; }
footer { color:var(--muted); font-size:13px; text-align:center; padding:20px; }
"""

JS = """
const data = window.SOLVERS;
const grid = document.getElementById('grid');
const q = document.getElementById('q');
const fy = document.getElementById('year'), ff = document.getElementById('family'), fv = document.getElementById('verdict'), fs = document.getElementById('status');
function badge(v) { const m = {verified:['Verified','ok'],runs:['Runs, checks failed','warn'],built:['Compiles','warn'],'source-available':['Build fails','fail'],'source-unavailable':['Source unavailable','fail'],unknown:['Not run yet','none']}[v] || [v,'none']; return `<span class="badge ${m[1]}">${m[0]}</span>`; }
function render() {
  const s = q.value.trim().toLowerCase();
  const fc = document.getElementById('cap');
  const rows = data.filter(d => (!fy.value || d.set === fy.value) && (!ff.value || d.family === ff.value) && (!fv.value || d.verdict === fv.value) && (!fs.value || d.status === fs.value) && (!fc.value || d.capabilities.includes(fc.value)) && (!s || (d.name + ' ' + d.key + ' ' + d.authors + ' ' + d.set).toLowerCase().includes(s)));
  document.getElementById('count').textContent = rows.length + ' / ' + data.length + ' images';
  grid.innerHTML = rows.map(d => `<a class="card" href="${d.set}/${d.key}.html">
    <h3>${d.name}</h3>
    <div class="meta">${d.set} · ${d.authors || 'authors not recorded'}</div>
    <div class="tagrow"><span class="lbl">solver</span><span class="tag id">${d.family}</span>${d.version ? `<span class="tag id">v${d.version}</span>` : ''}${d.tracks.map(t => `<span class="tag id">${t}</span>`).join('')}</div>
    <div class="tagrow"><span class="lbl">can do</span>${d.capabilities.map(c => `<span class="tag cap">${c}</span>`).join('')}</div>
    <div class="tagrow"><span class="lbl">status</span>${badge(d.verdict)}<span class="badge ${ {ok:'ok',unstable:'warn',fixme:'fail'}[d.status] || 'none'}">${ {ok:'builds',unstable:'unstable',fixme:'not buildable'}[d.status] || d.status}</span></div>
  </a>`).join('');
}
[q, fy, ff, fv, fs, document.getElementById('cap')].forEach(e => e.addEventListener('input', render));
render();
"""


def page(title: str, body: str, depth: int, active: str = "") -> str:
    root = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · SAT Heritage</title><link rel="stylesheet" href="{root}style.css"></head>
<body><header><a class="logo" href="{root}index.html" style="color:inherit"><span class="dot"></span>SAT Heritage</a>
<nav><a href="{root}index.html"{' class="active"' if active == 'overview' else ''}>Overview</a><a href="{root}catalogue.html"{' class="active"' if active == 'catalogue' else ''}>Catalogue</a><a href="{REPO_URL}">GitHub</a></nav>
<p>Docker images of SAT solvers, rebuilt from the competition sources and verified.</p></header>
<main>{body}</main>
<footer>Generated from the <a href="{REPO_URL}">sat-heritage/docker-images</a> repository.</footer></body></html>
"""


def index_page(solvers: list[dict]) -> str:
    years = sorted({s["set"] for s in solvers}, key=lambda y: (not y.isdigit(), -int(y) if y.isdigit() else 0))
    families = sorted({s["family"] for s in solvers})
    options = lambda values: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)
    body = f"""
<div class="toolbar">
  <input id="q" type="search" placeholder="Search a solver, an author, a year">
  <select id="year"><option value="">All years</option>{options(years)}</select>
  <select id="family"><option value="">All families</option>{options(families)}</select>
  <select id="verdict"><option value="">Any verification</option><option value="verified">Verified</option><option value="runs">Runs, checks failed</option><option value="built">Compiles</option><option value="source-available">Build fails</option><option value="source-unavailable">Source unavailable</option><option value="unknown">Not run yet</option></select>
  <select id="status"><option value="">Any status</option><option value="ok">builds</option><option value="unstable">unstable</option><option value="fixme">not buildable</option></select>
  <select id="cap"><option value="">Any capability</option><option value="SAT">SAT (verified)</option><option value="UNSAT">UNSAT (verified)</option><option value="UNSAT+proof">UNSAT+proof (verified)</option><option value="parallel">parallel</option><option value="gzip input">gzip input</option></select>
  <span class="count" id="count"></span>
</div>
<div class="legend"><span>◌ dashed: what the solver is</span><span>▪ blue: what it can do, as verified by the test suite</span><span>● filled: whether it builds and passes the tests today</span></div>
<div class="grid" id="grid"></div>
<script>window.SOLVERS = {json.dumps([{k: s[k] for k in ("image", "key", "set", "name", "authors", "status", "family", "verdict", "capabilities", "version", "tracks")} for s in solvers])};</script>
<script>{JS}</script>
"""
    return page("Catalogue", body, 0, "catalogue")


def solver_page(s: dict) -> str:
    vlabel, vcls = VERDICT_LABEL.get(s["verdict"], (s["verdict"], "none"))
    slabel, scls = STATUS_LABEL.get(s["status"], (s["status"], "none"))
    comp = COMPETITION_URL.get(int(s["set"])) if s["set"].isdigit() else None
    checks = "".join(
        f"<tr><td>{esc(k)}</td><td><span class='badge {'ok' if v['status']=='ok' else 'fail' if v['status']=='fail' else 'warn'}'>{esc(v['status'])}</span></td><td>{esc(v.get('detail',''))}</td></tr>"
        for k, v in s["checks"].items())
    stages = "".join(
        f"<tr><td>{esc(k)}</td><td><span class='badge {'ok' if v['status']=='ok' else 'fail' if v['status']=='fail' else 'warn'}'>{esc(v['status'])}</span></td><td>{esc(v.get('detail',''))}</td></tr>"
        for k, v in s["build_stages"].items())
    run_cmd = f"docker run --rm -v $PWD:/data {DOCKER_NS}/{s['image']} instance.cnf" + (" proof.out" if s["proof"] else "")
    body = f"""
<div class="crumbs"><a href="../catalogue.html">Catalogue</a> › {esc(s['set'])}</div>
<div class="page"><h1>{esc(s['name'])}</h1><div class="sub">{esc(s['authors'] or 'authors not recorded')}{(' · version ' + esc(s['version'])) if s['version'] else ''}</div>
<div class="tagrow" style="margin-top:10px"><span class="lbl">solver</span><span class="tag id">{esc(s['family'])}</span>{('<span class="tag id">v' + esc(s['version']) + '</span>') if s['version'] else ''}{''.join('<span class="tag id">' + esc(t) + '</span>' for t in s['tracks'])}</div>
<div class="tagrow" style="margin-top:6px"><span class="lbl">can do</span>{''.join('<span class="tag cap">' + esc(c) + '</span>' for c in s['capabilities']) or '<span class="tag cap">not verified yet</span>'}</div>
<div class="tagrow" style="margin-top:6px"><span class="lbl">status</span><span class="badge {vcls}">{vlabel}</span><span class="badge {scls}">{slabel}</span></div></div>
{('<div class="section"><h2>Status</h2><p>' + esc(s['status_detail']) + '</p></div>') if s['status_detail'] else ''}
{('<div class="section"><h2>Notes</h2><p>' + esc(s['comment']) + '</p></div>') if s['comment'] else ''}
<div class="section"><h2>Run it</h2><pre>{esc(run_cmd)}</pre><dl>
<dt>Image</dt><dd><code>{DOCKER_NS}/{esc(s['image'])}</code></dd>
<dt>Command</dt><dd><code>{esc(s['call'])} {esc(' '.join(map(str, s['args'])))}</code></dd>
<dt>Compressed input</dt><dd>{'read natively' if s['gz'] else 'decompressed by the image'}</dd>
{('<dt>Competition</dt><dd><a href="' + comp + '">SAT Competition ' + esc(s['set']) + '</a></dd>') if comp else ''}
</dl></div>
<div class="section"><h2>How it is built</h2><dl>
<dt>Recipe</dt><dd>{esc(s['recipe'])}</dd>
<dt>Builder</dt><dd><code>{esc(s['builder'])}</code></dd>
<dt>Environment</dt><dd><code>{esc(s['builder_base'])}</code>{(' · APT snapshot ' + esc(s['apt_snapshot'])) if s['apt_snapshot'] else ''}</dd>
{('<dt>Build command</dt><dd><code>' + esc(s['build_command']) + '</code></dd>') if s['build_command'] else ''}
{('<dt>Build dependencies</dt><dd>' + esc(s['build_depends']) + '</dd>') if s['build_depends'] else ''}
{('<dt>Runtime dependencies</dt><dd>' + esc(s['rdepends']) + '</dd>') if s['rdepends'] else ''}
{('<dt>Sources</dt><dd><a href="' + esc(s['download_url']) + '">' + esc(s['download_url'].rsplit('/', 1)[-1]) + '</a></dd>') if s['download_url'] else ''}
</dl></div>
<div class="section"><h2>Last verification</h2>
<p>{('Run on ' + esc(s['tested'][:10]) + '.') if s['tested'] else 'No recorded run.'}</p>
{('<h3>Build</h3><table>' + stages + '</table>') if stages else ''}
{('<h3>Tests</h3><table>' + checks + '</table>') if checks else ''}
</div>
"""
    return page(f"{s['name']} ({s['set']})", body, 1)


def svg_stacked_years(rows: list[tuple[str, dict]]) -> str:
    """Vertical stacked bars per year, one segment per rung of the verification ladder."""
    w, h, left, bottom, top = 900, 280, 36, 34, 18
    n = len(rows)
    inner = w - left - 12
    step = inner / max(n, 1)
    bw = min(34, step * 0.7)
    maxv = max((sum(c.values()) for _, c in rows), default=1) or 1
    scale = (h - top - bottom) / maxv
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Solver images per competition year and verification level">']
    for t in (0, maxv // 2, maxv):
        y = h - bottom - t * scale
        out.append(f'<line class="grid" x1="{left}" x2="{w-12}" y1="{y:.1f}" y2="{y:.1f}"/><text class="muted" x="{left-6}" y="{y+4:.1f}" text-anchor="end">{t}</text>')
    order = ["unknown"] + LADDER   # gray "not run yet" at the bottom, verified on top
    colors = {"unknown": "var(--l-none)", **{k: f"var(--l{i})" for i, k in enumerate(LADDER)}}
    for i, (year, counts) in enumerate(rows):
        x = left + i * step + (step - bw) / 2
        y = h - bottom
        total = sum(counts.values())
        tip = f"{year}: {total} images; " + ", ".join(f"{counts.get(k, 0)} {LADDER_LABEL.get(k, 'not run yet')}" for k in order if counts.get(k))
        for k in order:
            v = counts.get(k, 0)
            if not v:
                continue
            hv = v * scale
            y -= hv
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(hv-2,1):.1f}" rx="2" fill="{colors[k]}"><title>{esc(tip)}</title></rect>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" text-anchor="middle" class="muted">{total}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-bottom+16}" text-anchor="middle" class="muted">{year}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_hbars(rows: list[tuple[str, int]], label: str) -> str:
    """Horizontal single-series bars with direct value labels (sized for a half-width figure)."""
    w, rowh, left = 480, 22, 190
    h = rowh * len(rows) + 8
    maxv = max((v for _, v in rows), default=1) or 1
    scale = (w - left - 40) / maxv
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">']
    for i, (name, v) in enumerate(rows):
        y = i * rowh + 4
        out.append(f'<text x="{left-10}" y="{y+15}" text-anchor="end">{esc(name[:30])}</text>')
        out.append(f'<rect x="{left}" y="{y+3}" width="{v*scale:.1f}" height="{rowh-8}" rx="3" fill="var(--series-1)"><title>{esc(name)}: {v}</title></rect>')
        out.append(f'<text x="{left+v*scale+8:.1f}" y="{y+15}" class="muted">{v}</text>')
    out.append("</svg>")
    return "".join(out)


def overview_page(solvers: list[dict]) -> str:
    from collections import Counter
    years = sorted({s["set"] for s in solvers if s["set"].isdigit()}, key=int)
    per_year = [(y, Counter(s["verdict"] for s in solvers if s["set"] == y)) for y in years]
    authors = Counter()
    author_years = {}
    for s in solvers:
        for a in [a.strip() for a in re.split(r",|\band\b|&", s["authors"]) if a.strip()]:
            authors[a] += 1
            author_years.setdefault(a, set()).add(s["set"])
    families = Counter(s["family"] for s in solvers)
    verified = sum(1 for s in solvers if s["verdict"] == "verified")
    proofs = sum(1 for s in solvers if "UNSAT+proof" in s["capabilities"])
    top_authors = authors.most_common(12)
    top_families = [(f, c) for f, c in families.most_common(11) if f != "other"][:10]
    other_count = families.get("other", 0)
    longest = max(author_years.items(), key=lambda kv: (len(kv[1]), kv[0])) if author_years else ("", set())
    biggest_year = max(per_year, key=lambda r: sum(r[1].values())) if per_year else ("", Counter())
    compiles = sum(1 for s in solvers if s["verdict"] in ("built", "runs", "verified"))
    oldest = min((s for s in solvers if s["set"].isdigit()), key=lambda s: int(s["set"]), default=None)
    facts = [
        (f"{biggest_year[0]}", f"busiest year, {sum(biggest_year[1].values())} images"),
        (longest[0], f"present in {len(longest[1])} competition years, from {min(longest[1])} to {max(longest[1])}" if longest[1] else ""),
        (f"{proofs} images", "produce an UNSAT proof that the test suite verified"),
        (f"{len(authors)} authors", f"credited across {len(years)} competition years"),
        (oldest["set"] if oldest else "", f"first competition in the archive ({sum(1 for s in solvers if s['set'] == (oldest['set'] if oldest else '')) } images)"),
    ]
    body = f"""
<div class="hero"><h1>Every SAT competition solver, one <code>docker run</code> away.</h1>
<p>SAT Heritage rebuilds the solvers submitted to the SAT competitions from their original sources, in a build environment of their year, and verifies that each image still answers correctly. Browse the catalogue, or pull an image and run it on your instance.</p>
<a class="btn" href="catalogue.html">Browse the catalogue →</a></div>
<div class="stats">
<div class="stat"><div class="n">{len(solvers)}</div><div class="l">solver images</div></div>
<div class="stat"><div class="n">{compiles}</div><div class="l">compile from source today</div></div>
<div class="stat"><div class="n">{verified}</div><div class="l">verified today (build, SAT, UNSAT, proof)</div></div>
<div class="stat"><div class="n">{len(years)}</div><div class="l">competition years, {years[0]} to {years[-1]}</div></div>
<div class="stat"><div class="n">{len(families)}</div><div class="l">solver families</div></div>
<div class="stat"><div class="n">{len(authors)}</div><div class="l">authors</div></div>
</div>
<div class="fig"><h2>Solver images per competition year</h2><div class="sub">Each image sits on the highest rung it reached in its last run: source unavailable, source available but build fails, compiles, runs but a check fails, verified (build, SAT model, UNSAT and proof all pass). Gray: never run through the test suite yet.</div>
{svg_stacked_years(per_year)}
<div class="legend2"><span><i class="sw" style="background:var(--l-none)"></i>not run yet</span>{''.join(f'<span><i class="sw" style="background:var(--l{i})"></i>{LADDER_LABEL[k]}</span>' for i, k in enumerate(LADDER))}</div></div>
<div class="two" style="margin-top:14px">
<div class="fig"><h2>Most credited authors</h2><div class="sub">Number of solver images an author is credited on, all years together.</div>{svg_hbars(top_authors, "Most credited authors")}</div>
<div class="fig"><h2>Solver families</h2><div class="sub">Detected from the solver name and its executable; {other_count} images belong to no listed family.</div>{svg_hbars(top_families, "Solver families")}</div>
</div>
<div class="fig" style="margin-top:14px"><h2>Did you know?</h2><div class="facts">{''.join(f'<div class="fact"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in facts if a)}</div></div>
"""
    return page("Overview", body, 0, "overview")


def build(repo: Path, output: Path) -> int:
    solvers = collect(repo)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "style.css").write_text(CSS, encoding="utf-8")
    (output / "index.html").write_text(overview_page(solvers), encoding="utf-8")
    (output / "catalogue.html").write_text(index_page(solvers), encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    for s in solvers:
        set_dir = output / s["set"]
        set_dir.mkdir(exist_ok=True)
        (set_dir / f"{s['key']}.html").write_text(solver_page(s), encoding="utf-8")
    (output / "data.json").write_text(json.dumps(solvers, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(solvers)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("site"))
    args = parser.parse_args(argv)
    count = build(args.repo, args.output)
    print(f"[OK] {count} solver page(s) written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
