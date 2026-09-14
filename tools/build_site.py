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
    "passed": ("Verified", "ok"),
    "test-failed": ("Tests failed", "fail"),
    "build-failed": ("Build failed", "fail"),
    "not-tested": ("Built, not tested", "warn"),
    "unknown": ("Not run yet", "none"),
}
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
:root { --bg:#f7f7f8; --card:#fff; --ink:#1f2328; --muted:#656d76; --line:#d0d7de; --ok:#1a7f37; --warn:#9a6700; --fail:#cf222e; --none:#8c959f; --accent:#0969da; --cap:#0550ae; --capbg:#ddf4ff; }
@media (prefers-color-scheme: dark) { :root { --bg:#0d1117; --card:#161b22; --ink:#e6edf3; --muted:#8b949e; --line:#30363d; --ok:#3fb950; --warn:#d29922; --fail:#f85149; --none:#6e7681; --accent:#58a6ff; --cap:#79c0ff; --capbg:#0c2d6b; } }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bg); }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; } a.card:hover { text-decoration:none; border-color:var(--accent); }
header { padding:28px 24px 12px; border-bottom:1px solid var(--line); background:var(--card); }
header h1 { margin:0 0 4px; font-size:24px; } header p { margin:0; color:var(--muted); }
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
function badge(v) { const m = {passed:['Verified','ok'],'test-failed':['Tests failed','fail'],'build-failed':['Build failed','fail'],'not-tested':['Built, not tested','warn'],unknown:['Not run yet','none']}[v] || [v,'none']; return `<span class="badge ${m[1]}">${m[0]}</span>`; }
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


def page(title: str, body: str, depth: int) -> str:
    root = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · SAT Heritage</title><link rel="stylesheet" href="{root}style.css"></head>
<body><header><h1><a href="{root}index.html" style="color:inherit">SAT Heritage</a></h1><p>Docker images of SAT solvers, rebuilt from the competition sources and verified.</p></header>
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
  <select id="verdict"><option value="">Any verification</option><option value="passed">Verified</option><option value="test-failed">Tests failed</option><option value="build-failed">Build failed</option><option value="not-tested">Built, not tested</option><option value="unknown">Not run yet</option></select>
  <select id="status"><option value="">Any status</option><option value="ok">builds</option><option value="unstable">unstable</option><option value="fixme">not buildable</option></select>
  <select id="cap"><option value="">Any capability</option><option value="SAT">SAT (verified)</option><option value="UNSAT">UNSAT (verified)</option><option value="UNSAT+proof">UNSAT+proof (verified)</option><option value="parallel">parallel</option><option value="gzip input">gzip input</option></select>
  <span class="count" id="count"></span>
</div>
<div class="legend"><span>◌ dashed: what the solver is</span><span>▪ blue: what it can do, as verified by the test suite</span><span>● filled: whether it builds and passes the tests today</span></div>
<div class="grid" id="grid"></div>
<script>window.SOLVERS = {json.dumps([{k: s[k] for k in ("image", "key", "set", "name", "authors", "status", "family", "verdict", "capabilities", "version", "tracks")} for s in solvers])};</script>
<script>{JS}</script>
"""
    return page("Catalogue", body, 0)


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
<div class="crumbs"><a href="../index.html">Catalogue</a> › {esc(s['set'])}</div>
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


def build(repo: Path, output: Path) -> int:
    solvers = collect(repo)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "style.css").write_text(CSS, encoding="utf-8")
    (output / "index.html").write_text(index_page(solvers), encoding="utf-8")
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
