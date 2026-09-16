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
import urllib.parse
import html
import json
import re
import shutil
from pathlib import Path

DOCKER_NS = "satex"
REPO_URL = "https://github.com/sat-heritage/docker-images"
AUTHORS = "Gilles Audemard, Loïc Paulevé and Laurent Simon"
PAPER_TITLE = "SAT Heritage: a community-driven effort for archiving, building and running more than thousand SAT solvers"
PAPER_VENUE = "SAT 2020"
PAPER_URL = "https://doi.org/10.1007/978-3-030-51825-7_8"
PAPER_ARXIV = "https://arxiv.org/abs/2006.01503"
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
# Ladder colors (--l0..--l4): violet, orange, blue, amber, aqua; an ordered multi-hue set validated
# for colorblind separation and lightness in both themes (adjacent pairs, with the 2px gaps and the legend).
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
    hub_file = repo / "data" / "dockerhub.json"
    hub = load_json(hub_file) if hub_file.is_file() else {}
    published = set(hub.get("images", []))
    global HUB_GENERATED
    HUB_GENERATED = hub.get("generated", "")
    stats_file = repo / "data" / "stats.json"
    stats = load_json(stats_file) if stats_file.is_file() else {}
    pulls = stats.get("docker_hub", {}).get("repositories", {})
    downloads = stats.get("github_releases", {}).get("assets", {})
    global STATS_GENERATED, STATS_COMPLETE, ZENODO, GITHUB_DOWNLOADS
    STATS_GENERATED = stats.get("generated", "")
    STATS_COMPLETE = bool(stats.get("docker_hub", {}).get("complete"))
    ZENODO = stats.get("zenodo", {}).get("records", {})
    GITHUB_DOWNLOADS = sum(v.get("downloads", 0) for v in downloads.values())
    awards_file = repo / "data" / "awards.json"
    awards = load_json(awards_file).get("awards", []) if awards_file.is_file() else []
    awards_by_image = {}
    global MISSING_PODIUMS
    MISSING_PODIUMS = [a for a in awards if not a.get("solver")]
    for a in awards:
        if a.get("solver"):
            awards_by_image.setdefault(f"{a['solver']}:{a['year']}", []).append(a)
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
            if entry.get("incomplete"):
                capabilities = [c for c in capabilities if not c.startswith("UNSAT")] + ["SAT only (incomplete)"]
            elif not checks and "argsproof" not in entry:
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
                "license": entry.get("license", ""),
                "licenses": [x.strip() for x in re.split(r"\s+AND\s+", entry.get("license", "")) if x.strip()],
                "license_source": entry.get("license_source", ""),
                "awards": sorted(awards_by_image.get(image, []), key=lambda a: (a["rank"], a.get("category", "overall") != "overall", a["track"], a["category"])),
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
                "published": (f"{DOCKER_NS}/{image}" in published) if published else None,
                "pulls": pulls.get(key, {}).get("pulls") if key in pulls else None,
                "downloads": next((v["downloads"] for k2, v in downloads.items() if k2.split("/", 1)[1] == urllib.parse.unquote((block.get("download_url", "") or "").replace("{SOLVER_NAME}", entry.get("name", key)).rsplit("/", 1)[-1])), None) if downloads else None,
                "zenodo_record": (lambda m: m.group(1) if m else None)(re.search(r"zenodo\.org/records?/(\d+)", block.get("download_url", "") or "")),
                "verdict": result.get("verdict", "unknown"),
                "tested": result.get("date", ""),
                "build_stages": result.get("build", {}),
                "checks": result.get("tests", {}),
            })
    return solvers


CSS = """
.tag.lic{border-style:dotted}
.section.lic ul{margin:6px 0 0;padding-left:18px} .section.lic li{margin:6px 0}
.tag.award{border:1px solid transparent;font-weight:600}
.tag.award.r1{background:#fff3c4;color:#7a5a00;border-color:#e8c65a}
.tag.award.r2{background:#eceff3;color:#4a5361;border-color:#c3cad4}
.tag.award.r3{background:#f6e3d3;color:#7a4a1e;border-color:#dcb08c}
.tag.award::before{content:"★ ";opacity:.8}
.tag.award.more{background:var(--bg2);color:var(--muted);border-color:var(--line)} .tag.award.more::before{content:"✦ "}
.podium{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:10px}
.podium .yr{border:1px solid var(--border);border-radius:10px;padding:10px 12px;background:var(--surface)}
.podium .yr h3{margin:0 0 6px;font-size:15px}
.podium .yr div{font-size:13px;margin:3px 0}
.podium .yr small{color:var(--muted)}
.podium details{margin-top:6px} .podium summary{cursor:pointer;color:var(--accent);font-size:13px}
.badge.hub{background:#2496ed;color:#fff;border-color:#1d7fcc;display:inline-flex;align-items:center;gap:5px;text-decoration:none} a.badge.hub:hover{background:#1d7fcc;text-decoration:none}
.badge.hub.off{background:var(--bg2);color:var(--muted);border-color:var(--line)}
.badge.hub svg.docker{width:14px;height:14px;fill:currentColor;flex:none}
.pulls{color:var(--muted);font-size:12px;margin-left:auto;white-space:nowrap}
.links{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 10px} .btn.small{padding:6px 12px;font-size:13px}
.tabs{display:flex;gap:6px;margin:10px 0 14px} .tabs button{font:inherit;padding:8px 14px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);cursor:pointer}
.tabs button.active{background:var(--hf);border-color:var(--hfdark);color:#1a1a19;font-weight:600}
.lb{overflow-x:auto} .lb table{font-size:14px} .lb th{cursor:pointer;user-select:none;white-space:nowrap;color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--card)}
.lb th.sorted-desc::after{content:" ▾"} .lb th.sorted-asc::after{content:" ▴"} .lb td.num,.lb th.num{text-align:right;font-variant-numeric:tabular-nums}
.lb td.rank{color:var(--muted);width:2.5em} .lb tr.top1 td.rank{color:#7a5a00;font-weight:700} .lb tr.top2 td.rank{color:#4a5361;font-weight:700} .lb tr.top3 td.rank{color:#7a4a1e;font-weight:700}
.lb .medal{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle} .medal.g{background:#e8c65a} .medal.s{background:#c3cad4} .medal.b{background:#dcb08c}
.lb .who{color:var(--muted);font-size:13px}
:root { --bg:#ffffff; --bg2:#f8f9fb; --card:#ffffff; --ink:#0b0b0b; --muted:#5e6572; --line:#e5e7eb; --ok:#1a7f37; --warn:#9a6700; --fail:#cf222e; --none:#8c959f; --accent:#0b57d0; --hf:#ffd21e; --hfdark:#f59e0b; --cap:#0550ae; --capbg:#e8f1ff; --series-1:#2a78d6; --series-2:#eda100; --grid:#e5e7eb; --warnbg:#fff8dc; --l0:#4a3aa7; --l1:#eb6834; --l2:#2a78d6; --l3:#eda100; --l4:#1baf7a; --l-none:#d4d6da; }
@media (prefers-color-scheme: dark) { :root { --bg:#0b0f19; --bg2:#111827; --card:#161b26; --ink:#f3f4f6; --muted:#9aa3b2; --line:#2a3140; --ok:#3fb950; --warn:#d29922; --fail:#f85149; --none:#6e7681; --accent:#7ab4ff; --cap:#9ecbff; --capbg:#12305c; --series-1:#3987e5; --series-2:#c98500; --grid:#2a3140; --warnbg:#3a2f0b; --l0:#9085e9; --l1:#d95926; --l2:#3987e5; --l3:#c98500; --l4:#199e70; --l-none:#3a4150; } }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bg); }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; } a.card:hover { text-decoration:none; border-color:var(--accent); }
header { padding:16px 24px; border-bottom:1px solid var(--line); background:var(--card); display:flex; align-items:center; gap:18px; flex-wrap:wrap; }
header .logo { display:flex; align-items:center; gap:10px; font-weight:700; font-size:20px; } header .logo span.dot { width:26px; height:26px; border-radius:8px; background:var(--hf); display:inline-block; }
header nav a { margin-right:16px; color:var(--ink); font-weight:500; } header nav a.active { border-bottom:2px solid var(--hf); }
header p { margin:0; color:var(--muted); margin-left:auto; }
.warning { max-width:1200px; margin:16px auto 0; padding:12px 18px; border:1px solid var(--hfdark); border-left:6px solid var(--hf); background:var(--warnbg); border-radius:10px; font-size:15px; line-height:1.5; }
.hero { padding:28px 0 8px; } .hero .byline { color:var(--muted); font-size:14px; margin-bottom:10px; } .hero .byline b { color:var(--ink); font-weight:600; }
footer .credits { display:block; margin-bottom:6px; } .hero h1 { font-size:34px; margin:0 0 6px; } .hero p { color:var(--muted); font-size:17px; margin:0 0 18px; max-width:760px; }
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
.notice { font-size:14px !important; color:var(--muted); border-left:3px solid var(--hf); padding-left:10px; }
.muted-inline { color:var(--muted); font-size:13px; }
.pitch { margin:22px 0 6px; background:var(--card); border:1px solid var(--line); border-left:4px solid var(--hf); border-radius:12px; padding:14px 18px; max-width:860px; }
.pitch-head { font-weight:700; font-size:17px; margin-bottom:8px; } .pitch-foot { color:var(--muted); font-size:13px; margin-top:8px; }
.section.pull { border-left:4px solid var(--hf); }
pre.cmd { position:relative; padding-right:70px; } pre.cmd button { position:absolute; top:8px; right:8px; font:inherit; font-size:12px; padding:3px 9px; border-radius:6px; border:1px solid var(--line); background:var(--card); color:var(--ink); cursor:pointer; }
.btn { display:inline-block; background:var(--hf); color:#0b0b0b; padding:10px 16px; border-radius:10px; font-weight:600; } .btn:hover { text-decoration:none; filter:brightness(.95); }
main { max-width:1200px; margin:0 auto; padding:20px 24px 60px; }
.toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:8px 0 18px; padding:12px 14px; background:var(--bg2); border:1px solid var(--line); border-radius:14px; }
.ctl { display:inline-flex; align-items:center; gap:8px; padding:0 12px; border:1px solid var(--line); border-radius:999px; background:var(--card); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,.04); transition:border-color .15s, box-shadow .15s; }
.ctl:hover { border-color:var(--hfdark); } .ctl:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent); }
.ctl svg { width:16px; height:16px; flex:none; stroke:var(--muted); fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
.ctl:focus-within svg { stroke:var(--accent); }
.ctl input, .ctl select { font:inherit; padding:9px 0; border:0; background:transparent; color:var(--ink); outline:none; min-width:0; }
.ctl select { padding-right:4px; cursor:pointer; } .ctl.search { flex:1 1 260px; } .ctl.search input { width:100%; }
.ctl.award:has(option:checked:not([value=""])) { border-color:#e8c65a; background:#fff8dc; } .ctl.award:has(option:checked:not([value=""])) svg { stroke:#7a5a00; }
.count { color:var(--muted); margin-left:auto; font-size:14px; white-space:nowrap; }
@media (prefers-color-scheme: dark) { .ctl.award:has(option:checked:not([value=""])) { background:#3a2f0a; } }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:14px; }
section.year { display:grid; grid-template-columns:64px 1fr; gap:0 10px; padding:18px 0 10px; border-top:2px solid var(--line); }
section.year:first-child { border-top:0; padding-top:4px; }
.year-label { position:relative; } .year-label span { position:sticky; top:16px; display:block; writing-mode:vertical-rl; transform:rotate(180deg); font-weight:700; font-size:22px; color:var(--ink); letter-spacing:.04em; line-height:1; padding:2px 0; border-left:3px solid var(--hf); }
.year-label small { position:sticky; top:130px; display:block; color:var(--muted); font-size:12px; margin-top:8px; writing-mode:vertical-rl; transform:rotate(180deg); }
@media (max-width:640px) { section.year { grid-template-columns:1fr; } .year-label span, .year-label small { writing-mode:horizontal-tb; transform:none; border-left:0; border-bottom:3px solid var(--hf); display:inline-block; margin-right:10px; } }
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
footer { color:var(--muted); font-size:13px; text-align:center; padding:20px 24px 28px; max-width:900px; margin:0 auto; line-height:1.5; }
"""

JS = """
const data = window.SOLVERS;
const grid = document.getElementById('grid');
const q = document.getElementById('q');
const fy = document.getElementById('year'), ff = document.getElementById('family'), fv = document.getElementById('verdict'), fs = document.getElementById('status');
function badge(v) { const m = {verified:['Verified','ok'],runs:['Runs, checks failed','warn'],built:['Compiles','warn'],'source-available':['Build fails','fail'],'source-unavailable':['Source unavailable','fail'],unknown:['Not run yet','none']}[v] || [v,'none']; return `<span class="badge ${m[1]}">${m[0]}</span>`; }
function render() {
  const s = q.value.trim().toLowerCase();
  const fc = document.getElementById('cap'), fa = document.getElementById('award'), fh = document.getElementById('hub'), fl = document.getElementById('license');
  const rows = data.filter(d => (!fl.value || (fl.value === 'unknown' ? !d.licenses.length : d.licenses.includes(fl.value))) && (!fh || !fh.value || (fh.value === 'yes') === !!d.published) && (!fa.value || (fa.value === 'winner' ? d.awards.some(a => a.rank === 1) : d.awards.length > 0)) && (!fy.value || d.set === fy.value) && (!ff.value || d.family === ff.value) && (!fv.value || d.verdict === fv.value) && (!fs.value || d.status === fs.value) && (!fc.value || d.capabilities.includes(fc.value)) && (!s || (d.name + ' ' + d.key + ' ' + d.authors + ' ' + d.set).toLowerCase().includes(s)));
  document.getElementById('count').textContent = rows.length + ' / ' + data.length + ' images';
  const years = [...new Set(rows.map(d => d.set))].sort((a, b) => (isNaN(a) - isNaN(b)) || (b - a) || a.localeCompare(b));
  grid.innerHTML = years.map(y => `<section class="year"><div class="year-label"><span>${y}</span><small>${rows.filter(d => d.set === y).length}</small></div><div class="grid">` + rows.filter(d => d.set === y).map(card).join('') + `</div></section>`).join('');
}
function card(d) { return `<a class="card" href="${d.set}/${d.key}.html">
    <h3>${d.name}</h3>
    <div class="meta">${d.set} · ${d.authors || 'authors not recorded'}</div>
    <div class="tagrow"><span class="lbl">solver</span><span class="tag id">${d.family}</span>${d.version ? `<span class="tag id">v${d.version}</span>` : ''}${d.tracks.map(t => `<span class="tag id">${t}</span>`).join('')}${d.awards.slice(0, d.more ? 2 : 3).map(a => `<span class="tag award r${Math.min(a.rank, 3)}">${a.label}</span>`).join('')}${d.more ? `<span class="tag award more">${d.more}</span>` : ''}</div>
    <div class="tagrow"><span class="lbl">licence</span>${d.licenses.length ? d.licenses.map(l => `<span class="tag id lic">${l}</span>`).join('') : '<span class="tag id lic">licence unknown</span>'}</div>
    <div class="tagrow"><span class="lbl">can do</span>${d.capabilities.map(c => `<span class="tag cap">${c}</span>`).join('')}</div>
    <div class="tagrow"><span class="lbl">status</span>${badge(d.verdict)}<span class="badge ${ {ok:'ok',unstable:'warn',fixme:'fail'}[d.status] || 'none'}">${ {ok:'builds',unstable:'unstable',fixme:'not buildable'}[d.status] || d.status}</span>${d.published === true ? HUB_YES : d.published === false ? HUB_NO : ''}${d.pulls != null ? `<span class="pulls" title="pulls of satex/${d.key}, all tags">⇩ ${d.pulls.toLocaleString('en')}</span>` : ''}</div>
  </a>`; }
[q, fy, ff, fv, fs, document.getElementById('cap'), document.getElementById('award'), document.getElementById('hub'), document.getElementById('license')].filter(Boolean).forEach(e => e.addEventListener('input', render));
const params = new URLSearchParams(location.search);
for (const id of ['q', 'year', 'family', 'verdict', 'status', 'cap', 'award', 'hub', 'license']) { const v = params.get(id); if (v) { const el = document.getElementById(id); if (el) el.value = v; } }
render();
"""


RANK_LABEL = {1: "1st", 2: "2nd", 3: "3rd"}

# kind: permissive < weak-copyleft < strong-copyleft < non-commercial (strictest wins for the summary)
LICENSES = {
    "MIT": ("MIT License", "permissive", "Use, modify and redistribute freely, in source or binary form, as long as the copyright notice and the licence text stay with the code. This is MiniSat's licence, inherited by most of its descendants.", "https://spdx.org/licenses/MIT.html"),
    "BSD-2-Clause": ("BSD 2-Clause License", "permissive", "Use, modify and redistribute freely; keep the copyright notice and the disclaimer.", "https://spdx.org/licenses/BSD-2-Clause.html"),
    "BSD-3-Clause": ("BSD 3-Clause License", "permissive", "Use, modify and redistribute freely; keep the copyright notice and the disclaimer, and do not use the authors' names to endorse a derived product.", "https://spdx.org/licenses/BSD-3-Clause.html"),
    "Apache-2.0": ("Apache License 2.0", "permissive", "Use, modify and redistribute freely, with an explicit patent grant; keep the notices and state your changes.", "https://spdx.org/licenses/Apache-2.0.html"),
    "Unlicense": ("The Unlicense", "public-domain", "Public domain dedication: no conditions at all.", "https://spdx.org/licenses/Unlicense.html"),
    "CC-BY-4.0": ("Creative Commons Attribution 4.0", "permissive", "Share and adapt freely with attribution; a licence for data and documents more than for code.", "https://spdx.org/licenses/CC-BY-4.0.html"),
    "LGPL-2.0": ("GNU Library General Public License 2.0", "weak-copyleft", "The solver's code stays LGPL when modified and redistributed, but a program that only links to it can keep its own licence.", "https://spdx.org/licenses/LGPL-2.0.html"),
    "LGPL-2.1": ("GNU Lesser General Public License 2.1", "weak-copyleft", "The solver's code stays LGPL when modified and redistributed, but a program that only links to it can keep its own licence.", "https://spdx.org/licenses/LGPL-2.1.html"),
    "LGPL-3.0": ("GNU Lesser General Public License 3.0", "weak-copyleft", "The solver's code stays LGPL when modified and redistributed, but a program that only links to it can keep its own licence.", "https://spdx.org/licenses/LGPL-3.0.html"),
    "MPL-2.0": ("Mozilla Public License 2.0", "weak-copyleft", "Modified files must stay MPL and be published; the rest of a larger program can keep its own licence.", "https://spdx.org/licenses/MPL-2.0.html"),
    "EPL-1.0": ("Eclipse Public License 1.0", "weak-copyleft", "Modifications must be published under the EPL; a larger program can combine it with other licences (not with the GPL). Sat4j's licence.", "https://spdx.org/licenses/EPL-1.0.html"),
    "GPL-2.0": ("GNU General Public License 2.0", "strong-copyleft", "Any program that includes or links this code and is redistributed must be released under the GPL, sources included. Free to use and modify otherwise.", "https://spdx.org/licenses/GPL-2.0.html"),
    "GPL-3.0": ("GNU General Public License 3.0", "strong-copyleft", "Any program that includes or links this code and is redistributed must be released under the GPL, sources included. Free to use and modify otherwise.", "https://spdx.org/licenses/GPL-3.0.html"),
    "CC-BY-NC-4.0": ("Creative Commons Attribution-NonCommercial 4.0", "non-commercial", "Research and non-commercial use only; commercial use needs the authors' permission.", "https://spdx.org/licenses/CC-BY-NC-4.0.html"),
    "Proprietary": ("Proprietary or research-only terms", "non-commercial", "Redistributed here as in the competition; any other use is subject to the authors' own terms.", ""),
}
KIND_LABEL = {
    "public-domain": ("public domain", "ok", "No conditions at all."),
    "permissive": ("permissive", "ok", "You can use it, modify it and ship it in your own software, commercial or not, as long as you keep the copyright notices."),
    "weak-copyleft": ("weak copyleft", "warn", "You can use it in your own software, but changes to the solver itself must be published under the same licence."),
    "strong-copyleft": ("copyleft (GPL)", "warn", "You can use and modify it freely, but a program you redistribute with this solver inside must be GPL too, with its sources."),
    "non-commercial": ("non-commercial", "fail", "Research use only unless the authors agree otherwise."),
}
KIND_ORDER = ["public-domain", "permissive", "weak-copyleft", "strong-copyleft", "non-commercial"]


def license_summary(ids: list[str]) -> tuple[str, str, str]:
    """(label, badge class, sentence) for the strictest licence among ids; unknown ids are treated as unclassified."""
    kinds = [LICENSES[i][1] for i in ids if i in LICENSES]
    if not kinds:
        return ("unclassified", "none", "This licence is not in our table yet; read its text before reusing the code.")
    worst = max(kinds, key=KIND_ORDER.index)
    label, cls, sentence = KIND_LABEL[worst]
    if len(set(kinds)) > 1:
        sentence = "Components under different licences: the strictest one rules the whole. " + sentence
    return label, cls, sentence


def license_tags(ids: list[str], title: str = "") -> str:
    if not ids:
        return f'<span class="tag id lic" title="{esc(title or "licence not identified yet")}">licence unknown</span>'
    return "".join(f'<span class="tag id lic" title="{esc(title)}">{esc(i)}</span>' for i in ids)


def license_section(s: dict) -> str:
    ids = s["licenses"]
    label, cls, sentence = license_summary(ids)
    if not ids:
        return ('<div class="section lic"><h2>Licence</h2><p><span class="badge none">not identified</span> No licence file or recognizable licence header was found in the archived sources'
                + (f' ({esc(s["license_source"])})' if s["license_source"] else '') + '. SAT Heritage redistributes the sources as the competition did; before any other use, ask the authors. '
                f'If you know the licence, <a href="{REPO_URL}">send a pull request</a> adding a <code>license</code> field to this entry.</p></div>')
    def item(i: str) -> str:
        if i not in LICENSES:
            return f'<li><b>{esc(i)}</b> <span class="tag id lic">{esc(i)}</span><br><span class="muted-inline">Not in our table yet.</span></li>'
        name, kind, text, url = LICENSES[i]
        klabel, kcls, _ = KIND_LABEL[kind]
        link = f' <a href="{url}">Full text</a>' if url else ""
        return (f'<li><b>{esc(name)}</b> <span class="tag id lic">{esc(i)}</span> · <span class="badge {kcls}">{esc(klabel)}</span>'
                f'<br><span class="muted-inline">{esc(text)}{link}</span></li>')
    items = "".join(item(i) for i in ids)
    return (f'<div class="section lic"><h2>Licence</h2><p><span class="badge {cls}">{esc(label)}</span> {esc(sentence)}</p><ul>{items}</ul>'
            f'<p class="muted-inline">Read from {esc(s["license_source"]) if s["license_source"] else "the entry"}; this summary is informative, the licence text prevails. Corrections welcome by pull request.</p></div>')


def award_label(a: dict) -> str:
    """'1st · main track 2024', '2nd UNSAT · main track 2025', 'winner · AI subtrack 2026'."""
    rank = RANK_LABEL.get(a["rank"], f"{a['rank']}th")
    category = "" if a.get("category", "overall") == "overall" else " " + a["category"]
    return f"{rank}{category} · {a['track']} {a['year']}"


MAX_AWARD_TAGS = 2


def award_summary(awards: list[dict]) -> tuple[list[dict], str]:
    """The podiums shown as tags (best ones first), and the label of the aggregate badge for the rest."""
    shown = awards[:MAX_AWARD_TAGS] if len(awards) > MAX_AWARD_TAGS else awards
    rest = awards[len(shown):]
    if not rest:
        return shown, ""
    wins = sum(1 for a in rest if a["rank"] == 1)
    return shown, f"+{len(rest)} more podium{'s' if len(rest) > 1 else ''}" + (f" ({wins} win{'s' if wins > 1 else ''})" if wins else "")


def award_tags(awards: list[dict]) -> str:
    shown, more = award_summary(awards)
    tags = "".join(f'<span class="tag award r{min(a["rank"], 3)}" title="{esc(a.get("note", ""))}">{esc(award_label(a))}</span>' for a in shown)
    if more:
        tags += f'<span class="tag award more" title="{esc("; ".join(award_label(a) for a in awards[len(shown):]))}">{esc(more)}</span>'
    return tags


def page(title: str, body: str, depth: int, active: str = "") -> str:
    root = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · SAT Heritage</title><link rel="stylesheet" href="{root}style.css"></head>
<body><header><a class="logo" href="{root}index.html" style="color:inherit"><span class="dot"></span>SAT Heritage</a>
<nav><a href="{root}index.html"{' class="active"' if active == 'overview' else ''}>Overview</a><a href="{root}catalogue.html"{' class="active"' if active == 'catalogue' else ''}>Catalogue</a><a href="{root}leaderboards.html"{' class="active"' if active == 'leaderboards' else ''}>Leaderboards</a><a href="{root}missing.html"{' class="active"' if active == 'missing' else ''}>Missing solvers</a><a href="{REPO_URL}">GitHub</a></nav>
<p>Docker images of SAT solvers, from the first competitions to Knuth's programs, rebuilt from their sources and verified.</p></header>
<div class="warning"><b>September 14, 2026 — large update in progress.</b> The images of the 2022 to 2026 competitions are being rebuilt from their sources and pushed to Docker Hub in batches over the coming days. If <code>docker pull</code> tells you that an image does not exist yet, build it yourself in the meantime with <code>satex build &lt;solver&gt;:&lt;year&gt;</code> (<code>pip install satex</code>), from the same sources and recipe.</div>
<main>{body}</main>
<script>document.querySelectorAll('pre.cmd[data-copy]').forEach(p => {{ const b = document.createElement('button'); b.textContent = 'Copy'; b.addEventListener('click', () => {{ navigator.clipboard.writeText(p.innerText.replace(/Copy$/, '').trim()); b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1500); }}); p.appendChild(b); }});</script>
<footer><span class="credits">SAT Heritage is a project by {esc(AUTHORS)} · <a href="{PAPER_URL}">{esc(PAPER_TITLE)}</a> ({PAPER_VENUE}, <a href="{PAPER_ARXIV}">arXiv</a>)</span><br>Generated from the <a href="{REPO_URL}">sat-heritage/docker-images</a> repository. This site, its generator and the solver metadata it presents were assembled from scattered sources with the help of Claude Fable 5.1 since September 2026 (Anthropic): descriptions, author names, verification results and figures may be incomplete or wrong and should be checked against the repository and the original competition material before being relied upon. Corrections and contributions are welcome as issues or pull requests.</footer></body></html>
"""


ICON = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "year": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "family": '<path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
    "verdict": '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m9 11 3 3L22 4"/>',
    "status": '<path d="M12 2 4 5v6c0 5.5 3.8 10.7 8 12 4.2-1.3 8-6.5 8-12V5z"/>',
    "cap": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "hub": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>',
    "license": '<path d="M16 2H8a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2Z"/><path d="M9 7h6M9 11h6M9 15h4"/>',
    "award": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
}


def ctl(kind: str, control: str, extra_class: str = "") -> str:
    """A toolbar control (input or select) with its icon."""
    cls = f"ctl {kind} {extra_class}".strip()
    return f'<label class="{cls}"><svg viewBox="0 0 24 24" aria-hidden="true">{ICON[kind]}</svg>{control}</label>'


def index_page(solvers: list[dict]) -> str:
    years = sorted({s["set"] for s in solvers}, key=lambda y: (not y.isdigit(), -int(y) if y.isdigit() else 0))
    families = sorted({s["family"] for s in solvers})
    licenses = sorted({l for s in solvers for l in s["licenses"]})
    options = lambda values: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)
    body = f"""
<div class="toolbar">
  {ctl("search", '<input id="q" type="search" placeholder="Search a solver, an author, a year">')}
  {ctl("year", f'<select id="year"><option value="">All years</option>{options(years)}</select>')}
  {ctl("family", f'<select id="family"><option value="">All families</option>{options(families)}</select>')}
  {ctl("verdict", '<select id="verdict"><option value="">Any verification</option><option value="verified">Verified</option><option value="runs">Runs, checks failed</option><option value="built">Compiles</option><option value="source-available">Build fails</option><option value="source-unavailable">Source unavailable</option><option value="unknown">Not run yet</option></select>')}
  {ctl("status", '<select id="status"><option value="">Any status</option><option value="ok">builds</option><option value="unstable">unstable</option><option value="fixme">not buildable</option></select>')}
  {ctl("cap", '<select id="cap"><option value="">Any capability</option><option value="SAT">SAT (verified)</option><option value="UNSAT">UNSAT (verified)</option><option value="UNSAT+proof">UNSAT+proof (verified)</option><option value="SAT only (incomplete)">SAT only (incomplete solver)</option><option value="parallel">parallel</option><option value="gzip input">gzip input</option></select>')}
  {ctl("license", f'<select id="license"><option value="">Any licence</option>{options(licenses)}<option value="unknown">licence unknown</option></select>')}
  {ctl("award", '<select id="award"><option value="">Any award</option><option value="awarded">Awarded (any podium)</option><option value="winner">Winners (1st only)</option></select>')}
  {ctl("hub", '<select id="hub"><option value="">Docker Hub: any</option><option value="yes">Ready on Docker Hub</option><option value="no">Not on Docker Hub yet</option></select>') if HUB_GENERATED else ''}
  <span class="count" id="count"></span>
</div>
<div class="legend"><span>◌ dashed: what the solver is</span><span>▪ blue: what it can do, as verified by the test suite</span><span>● filled: whether it builds and passes the tests today</span></div>
<div id="grid"></div>
<script>window.SOLVERS = {json.dumps([dict({k: s[k] for k in ("image", "key", "set", "name", "authors", "status", "family", "verdict", "capabilities", "version", "tracks", "published", "licenses", "pulls")}, awards=[{"rank": a["rank"], "label": award_label(a)} for a in s["awards"]], more=award_summary(s["awards"])[1]) for s in solvers])};</script>
<script>const HUB_YES = {json.dumps(HUB_BADGE_YES.replace('<a class="badge hub" href="{url}" title="Tags of this image on Docker Hub">', '<span class="badge hub">').replace('</a>', '</span>'))}, HUB_NO = {json.dumps(HUB_BADGE_NO)};</script>
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
<div class="tagrow" style="margin-top:10px"><span class="lbl">solver</span><span class="tag id">{esc(s['family'])}</span>{('<span class="tag id">v' + esc(s['version']) + '</span>') if s['version'] else ''}{''.join('<span class="tag id">' + esc(t) + '</span>' for t in s['tracks'])}{award_tags(s['awards'])}</div>
<div class="tagrow" style="margin-top:6px"><span class="lbl">licence</span>{license_tags(s['licenses'], s['license_source'])}</div>
<div class="tagrow" style="margin-top:6px"><span class="lbl">can do</span>{''.join('<span class="tag cap">' + esc(c) + '</span>' for c in s['capabilities']) or '<span class="tag cap">not verified yet</span>'}</div>
<div class="tagrow" style="margin-top:6px"><span class="lbl">status</span><span class="badge {vcls}">{vlabel}</span><span class="badge {scls}">{slabel}</span>{hub_badge(s)}{(' <span class="muted-inline">' + fmt_count(s['pulls']) + ' pulls of satex/' + esc(s['key']) + ', all tags</span>') if s['pulls'] is not None else ''}</div></div>
{('<div class="section"><h2>Awards</h2><ul>' + ''.join('<li><span class="tag award r' + str(min(a['rank'], 3)) + '">' + esc(award_label(a)) + '</span>' + (' <span class="muted-inline">' + esc(a['note']) + '</span>' if a.get('note') else '') + ' <a class="muted-inline" href="' + esc(a['source']) + '">source</a></li>' for a in s['awards']) + '</ul></div>') if s['awards'] else ''}
{('<div class="section"><h2>Status</h2><p>' + esc(s['status_detail']) + '</p></div>') if s['status_detail'] else ''}
{('<div class="section"><h2>Notes</h2><p>' + esc(s['comment']) + '</p></div>') if s['comment'] else ''}
{license_section(s)}
<div class="section pull"><h2>{'Pull it from Docker and run it' if s['published'] is not False else 'Build it and run it'}</h2><pre class="cmd" data-copy>{'docker pull ' + DOCKER_NS + '/' + esc(s['image']) if s['published'] is not False else 'pip install satex && satex build ' + esc(s['image'])}
{esc(run_cmd)}</pre><p class="muted-inline">{('No build needed: the image is published on <a href="https://hub.docker.com/r/' + DOCKER_NS + '/' + esc(s['key']) + '">Docker Hub</a>' + (' (checked ' + esc(HUB_GENERATED[:10]) + ')' if HUB_GENERATED else '') + '.') if s['published'] is not False else ('This image is not on <a href="https://hub.docker.com/u/' + DOCKER_NS + '">Docker Hub</a> yet' + (' (checked ' + esc(HUB_GENERATED[:10]) + ')' if HUB_GENERATED else '') + ': the images are pushed in batches, and some entries cannot be built. Until then, <code>satex build</code> makes it on your machine from the archived sources and the recipe below, and the run command is the same.')} Mount the directory that holds your instance on <code>/data</code>; the proof file is optional{'' if s['proof'] else ' and not produced by this solver'}. Its full provenance is kept: the archived sources, the pinned build environment and the recipe are all listed below, and <code>satex build {esc(s['image'])}</code> rebuilds the same image on your own machine if you would rather not trust ours (slower, same solver).</p>
{('<p><a class="btn" href="' + esc(s['download_url']) + '">Download the sources</a> <span class="muted-inline">' + esc(urllib.parse.unquote(s['download_url'].rsplit('/', 1)[-1])) + ', the competition submission as archived by SAT Heritage, to build it yourself with the recipe below.' + ((' Downloaded ' + fmt_count(s['downloads']) + ' times.') if s['downloads'] is not None else ((' The Zenodo record holding the archives of this year was downloaded ' + fmt_count(ZENODO[s['zenodo_record']]['downloads']) + ' times (Zenodo counts per record, not per file).') if s['zenodo_record'] in ZENODO else '')) + '</span></p>') if s['download_url'] else ''}<dl>
<dt>Licence</dt><dd>{esc(', '.join(s['licenses'])) if s['licenses'] else 'not identified: no licence file or header found in the archive; if you know it, send a pull request'}{(' <span class="muted-inline">(' + esc(s['license_source']) + ')</span>') if s['license_source'] else ''}</dd>
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


def usage_figures(solvers: list[dict]) -> str:
    """Two bar charts: most pulled Docker Hub repositories and most downloaded source archives."""
    if not STATS_GENERATED:
        return ""
    by_key = {}
    for s in solvers:
        if s["pulls"] is not None:
            by_key[s["key"]] = s["pulls"]
    top_pulled = sorted(by_key.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    by_asset = {}
    for s in solvers:
        if s["downloads"] is not None and s["download_url"]:
            asset = urllib.parse.unquote(s["download_url"].rsplit("/", 1)[-1])
            by_asset.setdefault(asset, (s["downloads"], f'{s["name"]} ({s["set"]})'))
    top_dl = sorted(((label, count) for count, label in by_asset.values()), key=lambda t: (-t[1], t[0]))[:10]
    if not top_pulled and not top_dl:
        return ""
    note = " Our own builds and verification runs are counted."
    left = (f'<div class="fig"><h2>Most pulled solvers</h2><div class="sub">Docker Hub pulls per repository, all years of a solver together, read on {esc(STATS_GENERATED[:10])}.'
            f'{"" if STATS_COMPLETE else " Only the first 100 repositories could be read."}{note} <a href="leaderboards.html#pulled">Full list →</a></div>{svg_hbars(top_pulled, "Most pulled solvers")}</div>') if top_pulled else ""
    right = (f'<div class="fig"><h2>Most downloaded sources</h2><div class="sub">Downloads of the source archives from the GitHub releases, read on {esc(STATS_GENERATED[:10])}. Zenodo only counts downloads per record, so the years hosted there appear in the next figure.{note}</div>{svg_hbars(top_dl, "Most downloaded sources")}</div>') if top_dl else ""
    by_year = {}
    for s in solvers:
        y = by_year.setdefault(s["set"], {"assets": {}, "records": set()})
        if s["downloads"] is not None and s["download_url"]:
            y["assets"][urllib.parse.unquote(s["download_url"].rsplit("/", 1)[-1])] = s["downloads"]
        if s["zenodo_record"] in ZENODO:
            y["records"].add(s["zenodo_record"])
    rows = [(f'{y} ({"Zenodo" if d["records"] else "GitHub"})', sum(d["assets"].values()) + sum(ZENODO[r]["downloads"] for r in d["records"]))
            for y, d in sorted(by_year.items()) if d["assets"] or d["records"]]
    per_year = (f'<div class="fig"><h2>Source downloads by competition year</h2><div class="sub">Downloads of the archives of each year: the release assets on GitHub, or the Zenodo record of the year (2000 to 2005 hold binaries only).{note}</div>{svg_hbars(rows, "Source downloads by competition year")}</div>') if rows else ""
    return f'<div class="two" style="margin-top:14px">{left}{right}</div>' + (f'<div class="two" style="margin-top:14px">{per_year}</div>' if per_year else "")


def podium_section(solvers: list[dict]) -> str:
    """Award-winning solvers per year, from data/awards.json (sequential tracks only)."""
    by_year = {}
    for s in solvers:
        for a in s["awards"]:
            by_year.setdefault(a["year"], []).append((a, s))
    if not by_year:
        return ""
    def line(a, s):
        return (f'<div><span class="tag award r{min(a["rank"], 3)}">{esc(award_label(a).split(" · ")[0])}</span> '
                f'<a href="{s["set"]}/{s["key"]}.html">{esc(s["name"])}</a> <small>{esc(a["track"])}'
                f'{("" if a.get("category", "overall") == "overall" else ", " + esc(a["category"]))}</small></div>')
    blocks = []
    for year in sorted(by_year, reverse=True):
        rows = sorted(by_year[year], key=lambda t: (t[0]["track"] not in ("main track", "application track", "industrial track"), t[0]["track"], t[0].get("category", "overall") not in ("overall", "SAT+UNSAT"), t[0].get("category", ""), t[0]["rank"]))
        winners = [(a, s) for a, s in rows if a["rank"] == 1]
        rest = [(a, s) for a, s in rows if a["rank"] != 1]
        tracks = len({a["track"] for a, _ in rows})
        body = "".join(line(a, s) for a, s in winners)
        if rest:
            body += f'<details><summary>{len(rest)} more podium place{"s" if len(rest) > 1 else ""}</summary>{"".join(line(a, s) for a, s in rest)}</details>'
        blocks.append(f'<div class="yr"><h3>{year} <small>{tracks} track{"s" if tracks > 1 else ""}</small></h3>{body}</div>')
    first = min(by_year)
    return (f'<div class="fig" style="margin-top:14px"><h2>Award-winning solvers</h2><div class="sub">Winners of every track and category as announced by the competition organizers, {first} to {max(by_year)}, with the rest of each podium folded. Ties share a rank; only podiums whose solver has an image here are listed, see <a href="{REPO_URL}/blob/webpage/data/awards.json">data/awards.json</a> for the sources. This summary is an extraction from the database and involves choices and interpretations that may still change (some solver names are not clarified yet); any help is welcome, send a pull request.</div>'
            f'<div class="links"><a class="btn small" href="catalogue.html?award=winner">Winners in the catalogue →</a> <a class="btn small" href="catalogue.html?award=awarded">Every awarded solver →</a> <a class="btn small" href="leaderboards.html">Leaderboards →</a></div>'
            f'<div class="podium">{"".join(blocks)}</div></div>')


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
    tested = sum(1 for s in solvers if s["verdict"] != "unknown")
    oldest = min((s for s in solvers if s["set"].isdigit()), key=lambda s: int(s["set"]), default=None)
    facts = [
        (f"{biggest_year[0]}", f"busiest year, {sum(biggest_year[1].values())} images"),
        (longest[0], f"present in {len(longest[1])} competition years, from {min(longest[1])} to {max(longest[1])}" if longest[1] else ""),
        (f"{proofs} images", "produce an UNSAT proof that the test suite verified"),
        (f"{len(authors)} authors", f"credited across {len(years)} competition years"),
        (oldest["set"] if oldest else "", f"first competition in the archive ({sum(1 for s in solvers if s['set'] == (oldest['set'] if oldest else '')) } images)"),
    ]
    body = f"""
<div class="hero"><div class="byline">A project by <b>{esc(AUTHORS)}</b> · tool paper: <a href="{PAPER_URL}">{esc(PAPER_TITLE)}</a>, {PAPER_VENUE} (<a href="{PAPER_ARXIV}">arXiv</a>)</div>
<h1>Thirty years of SAT solvers, one <code>docker run</code> away.</h1>
<p>SAT Heritage archives and rebuilds SAT solvers from their original sources, in a build environment of their time, and verifies that each image still answers correctly: every solver submitted to the SAT competitions since 2002, but also historical releases and programs that never entered a competition, such as Donald Knuth's SAT solvers from <em>The Art of Computer Programming</em>. Browse the catalogue, or pull an image and run it on your instance.</p>
<p class="notice">Everything here was assembled from scattered sources, competition archives, proceedings, run scripts and README files, with the help of Claude Fable 5.1 since September 2026, and is reported with caution: despite our efforts, author names may be missing or wrong, versions approximate, and some solvers may not build or run as they did in competition. Contributions are welcome, from a corrected author line to a fixed recipe: open an issue or a pull request on <a href="{REPO_URL}">GitHub</a>.</p>
<a class="btn" href="catalogue.html">Browse the catalogue →</a>
<div class="pitch"><div class="pitch-head">No compiler, no dependencies: pull it from Docker and run it.</div>
<pre class="cmd" data-copy>docker pull satex/kissat-sc2024:2024
docker run --rm -v $PWD:/data satex/kissat-sc2024:2024 instance.cnf proof.out</pre>
<div class="pitch-foot">Every solver is an image on <a href="https://hub.docker.com/u/satex">Docker Hub</a>, named <code>satex/&lt;solver&gt;:&lt;year&gt;</code>. Give it a DIMACS file, and a proof file if you want one. The <a href="{REPO_URL}#satex-python-script">satex</a> script (<code>pip install satex</code>) lists, runs and extracts them in one line.</div>
<div class="pitch-foot"><b>Don't trust, verify.</b> Nothing is hidden: each image carries the full provenance of its build, the archived competition sources, the exact build environment (a Debian image pinned by digest and a dated package snapshot) and the recipe, all versioned in the repository and shown on every solver page. If you would rather not trust our images, <code>satex build &lt;solver&gt;:&lt;year&gt;</code> rebuilds them on your machine from the same sources with the same recipe. It takes longer, but you get the same solver.</div></div></div>
<div class="stats">
<div class="stat"><div class="n">{len(solvers)}</div><div class="l">solver images</div></div>
<div class="stat"><div class="n">{tested}</div><div class="l">run through the test suite so far</div></div>
<div class="stat"><div class="n">{compiles}</div><div class="l">of them compile from source today</div></div>
<div class="stat"><div class="n">{verified}</div><div class="l">of them fully verified (build, SAT, UNSAT, proof)</div></div>
{('<div class="stat"><div class="n">' + fmt_count(sum(s["pulls"] or 0 for s in {x["key"]: x for x in solvers}.values())) + '</div><div class="l">Docker Hub pulls' + ('' if STATS_COMPLETE else ' (first 100 repositories only)') + ', our own builds and tests included</div></div><div class="stat"><div class="n">' + fmt_count(GITHUB_DOWNLOADS + sum(v.get("downloads", 0) for v in ZENODO.values())) + '</div><div class="l">source archive downloads, GitHub releases and Zenodo records together</div></div>') if STATS_GENERATED else ''}
{('<div class="stat"><div class="n">' + str(sum(1 for s in solvers if s["published"])) + '</div><div class="l">images on Docker Hub, checked ' + esc(HUB_GENERATED[:10]) + '</div></div>') if HUB_GENERATED else ''}
<div class="stat"><div class="n">{len(years)}</div><div class="l">competition years, {years[0]} to {years[-1]}</div></div>
<div class="stat"><div class="n">{sum(1 for s in solvers if s["license"])}</div><div class="l">images with an identified licence (<a href="catalogue.html?license=unknown">{sum(1 for s in solvers if not s["license"])} unknown</a>)</div></div>
<div class="stat"><div class="n">{len(families)}</div><div class="l">solver families</div></div>
<div class="stat"><div class="n">{len(authors)}</div><div class="l">authors</div></div>
</div>
<div class="fig"><h2>Solver images per competition year</h2><div class="sub">Each image sits on the highest rung it reached in its last run: source unavailable, source available but build fails, compiles, runs but a check fails, verified (build, SAT model, UNSAT and proof all pass). Gray: never run through the test suite yet.</div>
{svg_stacked_years(per_year)}
<div class="legend2"><span><i class="sw" style="background:var(--l-none)"></i>not run yet</span>{''.join(f'<span><i class="sw" style="background:var(--l{i})"></i>{LADDER_LABEL[k]}</span>' for i, k in enumerate(LADDER))}</div></div>
<div class="two" style="margin-top:14px">
<div class="fig"><h2>Most credited authors</h2><div class="sub">Number of solver images an author is credited on, all years together. Author lists are still being cleaned up, from submitter names to full credits: if you do not find yourself, send a pull request.</div>{svg_hbars(top_authors, "Most credited authors")}</div>
<div class="fig"><h2>Solver families</h2><div class="sub">Detected from the solver name and its executable; {other_count} images belong to no listed family. Work in progress: a misplaced or missing family is one pull request away.</div>{svg_hbars(top_families, "Solver families")}</div>
</div>
{podium_section(solvers)}
{usage_figures(solvers)}
<div class="fig" style="margin-top:14px"><h2>Did you know?</h2><div class="facts">{''.join(f'<div class="fact"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in facts if a)}</div></div>
"""
    return page("Overview", body, 0, "overview")


MISSING_PODIUMS: list[dict] = []
HUB_GENERATED = ""
STATS_GENERATED = ""
STATS_COMPLETE = False
ZENODO = {}
GITHUB_DOWNLOADS = 0


def fmt_count(n) -> str:
    return f"{n:,}".replace(",", "\u202f")
DOCKER_MARK = ('<svg class="docker" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 9h3v3H5zM9 9h3v3H9zM13 9h3v3h-3zM9 5h3v3H9zM13 5h3v3h-3zM17 9h3v3h-3z"/>'
               '<path d="M2 13h18.3c1.2 0 2.3-.4 3.2-1.2l.5-.5-1-.5c-.9-.4-2-.5-3-.3-.2-1-.8-1.8-1.7-2.3l-.4-.2-.3.4c-.6.9-.7 2-.3 3H2v.5C2 17 5 21 10.5 21c5.2 0 8.6-2.4 10.4-6.2-3.3.6-6.3-.3-7.9-1.8H2z"/></svg>')
HUB_BADGE_YES = f'<a class="badge hub" href="{{url}}" title="Tags of this image on Docker Hub">{DOCKER_MARK}Ready on Docker Hub</a>'
HUB_BADGE_NO = f'<span class="badge hub off">{DOCKER_MARK}Not on Docker Hub yet</span>'


def hub_url(key: str, tag: str) -> str:
    return f"https://hub.docker.com/r/{DOCKER_NS}/{key}/tags?name={tag}"


def hub_badge(s: dict) -> str:
    if s["published"] is None:
        return ""
    return HUB_BADGE_YES.replace("{url}", esc(hub_url(s["key"], s["set"]))) if s["published"] else HUB_BADGE_NO
NO_SOURCE = re.compile(r"(no|miss(es|ing)?|without|lost) (the )?sources?|binary[- ]only|only (a )?binary|precompiled only|sources? (are )?(unavailable|missing|not available)", re.I)


def source_problem(s: dict) -> str:
    """Why an image has no usable source, or '' when it has one."""
    if s["verdict"] == "source-unavailable":
        return "the archived source could not be downloaded in the last test run"
    if not s["download_url"]:
        return "no source archive is referenced for this entry"
    text = f"{s['status_detail']} {s['comment']}"
    m = NO_SOURCE.search(text)
    if m:
        return text.strip()
    return ""


def missing_page(solvers: list[dict]) -> str:
    """Solvers whose sources are missing: images without a usable source, and podiums whose solver is absent from the archive."""
    no_source = [(s, source_problem(s)) for s in solvers]
    no_source = [(s, why) for s, why in no_source if why]
    no_source.sort(key=lambda t: (t[0]["set"], t[0]["name"].lower()))
    rows1 = "".join(
        f'<tr><td><a href="{s["set"]}/{s["key"]}.html">{esc(s["name"])}</a></td><td>{esc(s["set"])}</td><td class="who">{esc(s["authors"] or "authors not recorded")}</td><td>{esc(why)}</td></tr>'
        for s, why in no_source)
    podiums = sorted(MISSING_PODIUMS, key=lambda a: (-a["year"], a["track"], a["category"], a["rank"]))
    rows2 = "".join(
        f'<tr><td>{esc(a.get("competition_name") or "?")}</td><td>{a["year"]}</td><td><span class="tag award r{min(a["rank"], 3)}">{esc(award_label(a))}</span></td>'
        f'<td class="who">{esc(a.get("note", ""))}{" " if a.get("note") else ""}<a href="{esc(a.get("source", "#"))}">source</a></td></tr>'
        for a in podiums)
    body = f"""
<div class="page"><h1>Missing solvers</h1><div class="sub">What the archive lacks, and where you can help. SAT Heritage only keeps solvers it can rebuild from source: for the entries below the source is lost, was never published, or is a binary only. If you have a copy, or know where one survives, open an issue or a pull request on <a href="{REPO_URL}">GitHub</a>; <a href="{REPO_URL}/blob/master/SOURCES.md">SOURCES.md</a> lists where every year's archives are hosted.</div></div>
<div class="fig"><h2>Images without a usable source ({len(no_source)})</h2><div class="sub">Entries of the catalogue whose source archive is missing, binary-only, or could not be fetched in the last test run. The list grows as the test suite reaches the older years.</div>
<div class="lb"><table><thead><tr><th>Solver</th><th>Year</th><th>Authors</th><th>Problem</th></tr></thead><tbody>{rows1 or '<tr><td colspan="4">none known</td></tr>'}</tbody></table></div></div>
<div class="fig" style="margin-top:14px"><h2>Solvers without an identified licence ({sum(1 for s in solvers if not s["license"])})</h2><div class="sub">Their archive carries neither a licence file nor a licence header that we recognize. SAT Heritage redistributes competition sources as the competitions did; if you are an author, tell us the licence of your solver (an issue or a pull request adding a <code>license</code> field to its entry is enough). <a href="catalogue.html?license=unknown">See them in the catalogue →</a></div></div>
<div class="fig" style="margin-top:14px"><h2>Award-winning solvers absent from the archive ({len(podiums)})</h2><div class="sub">Podium places announced by the competition organizers whose solver has no image here: the entry was never archived, or the archive holds a different variant and the mapping is unresolved. Contributions welcome, from the sources themselves to a pointer to the right variant.</div>
<div class="lb"><table><thead><tr><th>Competition name</th><th>Year</th><th>Podium</th><th>Notes</th></tr></thead><tbody>{rows2 or '<tr><td colspan="4">none</td></tr>'}</tbody></table></div></div>
<script>{LB_JS}</script>
"""
    return page("Missing solvers", body, 0, "missing")


LB_JS = """
const tabs = document.querySelectorAll('.tabs button'), panes = document.querySelectorAll('.pane');
function showTab(name) { tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === name)); panes.forEach(p => p.hidden = p.id !== name); history.replaceState(null, '', '#' + name); }
tabs.forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
showTab(['#authors', '#pulled'].includes(location.hash) ? location.hash.slice(1) : 'solvers');
document.querySelectorAll('.lb table').forEach(table => {
  const tbody = table.tBodies[0];
  table.querySelectorAll('th').forEach((th, i) => th.addEventListener('click', () => {
    const num = th.classList.contains('num'), desc = !th.classList.contains('sorted-desc');
    table.querySelectorAll('th').forEach(h => h.classList.remove('sorted-desc', 'sorted-asc'));
    th.classList.add(desc ? 'sorted-desc' : 'sorted-asc');
    const rows = [...tbody.rows];
    rows.sort((a, b) => { const x = a.cells[i].dataset.v ?? a.cells[i].textContent.trim(), y = b.cells[i].dataset.v ?? b.cells[i].textContent.trim();
      const c = num ? (parseFloat(x) || 0) - (parseFloat(y) || 0) : x.localeCompare(y, undefined, {numeric: true, sensitivity: 'base'}); return desc ? -c : c; });
    rows.forEach(r => tbody.appendChild(r));
  }));
  const search = table.parentElement.querySelector('input[type=search]');
  if (search) search.addEventListener('input', () => { const s = search.value.trim().toLowerCase(); [...tbody.rows].forEach(r => r.hidden = !!s && !r.textContent.toLowerCase().includes(s)); });
});
"""

POINTS = {1: 3, 2: 2, 3: 1}


def author_names(text: str) -> list[str]:
    """Individual author names from a credit line; submitter placeholders are dropped."""
    if not text or text.lower().startswith("submitted by"):
        return []
    text = re.sub(r"\(.*?\)", "", text)
    names = [a.strip(" .") for a in re.split(r",|\band\b|&|;", text)]
    return [a for a in names if a and "co-author" not in a.lower() and "et al" not in a.lower() and len(a) > 2]


def leaderboard_page(solvers: list[dict]) -> str:
    """Solvers and authors ranked by competition medals (3 points per gold, 2 per silver, 1 per bronze)."""
    def medals(awards):
        g = sum(1 for a in awards if a["rank"] == 1); sv = sum(1 for a in awards if a["rank"] == 2); b = sum(1 for a in awards if a["rank"] == 3)
        return g, sv, b, 3 * g + 2 * sv + b
    rows = []
    for s in solvers:
        if not s["awards"]:
            continue
        g, sv, b, pts = medals(s["awards"])
        rows.append((pts, g, sv, b, s))
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], -r[3], r[4]["set"], r[4]["name"].lower()))
    vlab = lambda s: VERDICT_LABEL.get(s["verdict"], (s["verdict"], "none"))
    solver_rows = "".join(
        f'<tr class="top{i + 1 if i < 3 else 0}"><td class="rank" data-v="{i + 1}">{i + 1}</td>'
        f'<td><a href="{s["set"]}/{s["key"]}.html">{esc(s["name"])}</a> <span class="tag id">{esc(s["family"])}</span></td>'
        f'<td data-v="{esc(s["set"])}">{esc(s["set"])}</td><td class="who">{esc(s["authors"] or "authors not recorded")}</td>'
        f'<td class="num" data-v="{g}">{g}</td><td class="num" data-v="{sv}">{sv}</td><td class="num" data-v="{b}">{b}</td><td class="num" data-v="{pts}"><b>{pts}</b></td>'
        f'<td class="num" data-v="{len({a["track"] for a in s["awards"]})}">{len({a["track"] for a in s["awards"]})}</td>'
        f'<td data-v="{esc(s["verdict"])}"><span class="badge {vlab(s)[1]}">{esc(vlab(s)[0])}</span></td></tr>'
        for i, (pts, g, sv, b, s) in enumerate(rows))
    authors = {}
    for s in solvers:
        for a in author_names(s["authors"]):
            d = authors.setdefault(a, {"images": 0, "years": set(), "awards": [], "awarded": set(), "best": None})
            d["images"] += 1
            d["years"].add(s["set"])
            if s["awards"]:
                d["awards"] += s["awards"]
                d["awarded"].add(s["image"])
                pts = medals(s["awards"])[3]
                if d["best"] is None or pts > d["best"][0]:
                    d["best"] = (pts, s)
    arows = []
    for name, d in authors.items():
        if not d["awards"]:
            continue
        g, sv, b, pts = medals(d["awards"])
        arows.append((pts, g, sv, b, name, d))
    arows.sort(key=lambda r: (-r[0], -r[1], -r[2], -r[3], r[4].lower()))
    def years_text(ys):
        ys = sorted(y for y in ys if y.isdigit())
        return f"{ys[0]}–{ys[-1]}" if len(ys) > 1 else (ys[0] if ys else "")
    author_rows = "".join(
        f'<tr class="top{i + 1 if i < 3 else 0}"><td class="rank" data-v="{i + 1}">{i + 1}</td>'
        f'<td><a href="catalogue.html?q={esc(name)}">{esc(name)}</a></td>'
        f'<td class="num" data-v="{g}">{g}</td><td class="num" data-v="{sv}">{sv}</td><td class="num" data-v="{b}">{b}</td><td class="num" data-v="{pts}"><b>{pts}</b></td>'
        f'<td class="num" data-v="{len(d["awarded"])}">{len(d["awarded"])}</td><td class="num" data-v="{d["images"]}">{d["images"]}</td>'
        f'<td data-v="{esc(years_text(d["years"]))}">{esc(years_text(d["years"]))}</td>'
        f'<td><a href="{d["best"][1]["set"]}/{d["best"][1]["key"]}.html">{esc(d["best"][1]["name"])}</a> <span class="who">{esc(d["best"][1]["set"])}</span></td></tr>'
        for i, (pts, g, sv, b, name, d) in enumerate(arows))
    # most pulled repositories on Docker Hub (a repository gathers every year of a solver key)
    by_key = {}
    for s in solvers:
        if s["pulls"] is not None:
            by_key.setdefault(s["key"], {"pulls": s["pulls"], "images": []})["images"].append(s)
    prow_list = sorted(by_key.items(), key=lambda kv: (-kv[1]["pulls"], kv[0]))[:200]
    def years_links(images):
        return " ".join('<a href="' + im["set"] + "/" + im["key"] + '.html">' + esc(im["set"]) + "</a>" for im in sorted(images, key=lambda x: x["set"]))
    pulled_rows = "".join(
        f'<tr class="top{i + 1 if i < 3 else 0}"><td class="rank" data-v="{i + 1}">{i + 1}</td>'
        f'<td><a href="https://hub.docker.com/r/{DOCKER_NS}/{esc(key)}/tags">{DOCKER_NS}/{esc(key)}</a></td>'
        f'<td>{years_links(d["images"])}</td>'
        f'<td class="who">{esc(d["images"][0]["authors"] or "authors not recorded")}</td>'
        f'<td class="num" data-v="{d["pulls"]}"><b>{fmt_count(d["pulls"])}</b></td></tr>'
        for i, (key, d) in enumerate(prow_list))
    head_medals = '<th class="num"><span class="medal g"></span>Gold</th><th class="num"><span class="medal s"></span>Silver</th><th class="num"><span class="medal b"></span>Bronze</th><th class="num">Points</th>'
    body = f"""
<div class="page"><h1>Leaderboards</h1><div class="sub">Solvers and authors ranked by competition medals: 3 points per gold, 2 per silver, 1 per bronze, every track and category counted, as recorded in <a href="{REPO_URL}/blob/webpage/data/awards.json">data/awards.json</a>. Only solvers with an image here are counted, so this is a view of the archive, not the official history; podiums and credits are still being clarified, corrections welcome by pull request. Click a column to sort.</div></div>
<div class="tabs"><button data-tab="solvers">Solvers ({len(rows)})</button><button data-tab="authors">Authors ({len(arows)})</button>{('<button data-tab="pulled">Most pulled (' + str(len(prow_list)) + ')</button>') if prow_list else ''}</div>
<section id="solvers" class="pane fig"><div class="toolbar">{ctl("search", '<input type="search" placeholder="Filter solvers, authors, years">')}</div><div class="lb"><table>
<thead><tr><th class="num">#</th><th>Solver</th><th>Year</th><th>Authors</th>{head_medals}<th class="num">Tracks</th><th>Status</th></tr></thead><tbody>{solver_rows}</tbody></table></div></section>
<section id="authors" class="pane fig" hidden><div class="toolbar">{ctl("search", '<input type="search" placeholder="Filter authors">')}</div><div class="lb"><table>
<thead><tr><th class="num">#</th><th>Author</th>{head_medals}<th class="num">Awarded solvers</th><th class="num">Images</th><th>Years</th><th>Best solver</th></tr></thead><tbody>{author_rows}</tbody></table></div></section>
{('<section id="pulled" class="pane fig" hidden><div class="sub">Docker Hub pull counts per repository (all years of a solver together), as read on ' + esc(STATS_GENERATED[:10]) + '; they include the pulls made by our own builds and verification runs' + ('' if STATS_COMPLETE else ', and only the first 100 repositories could be read') + '.</div><div class="toolbar">' + ctl("search", '<input type="search" placeholder="Filter repositories">') + '</div><div class="lb"><table><thead><tr><th class="num">#</th><th>Repository</th><th>Years</th><th>Authors</th><th class="num">Pulls</th></tr></thead><tbody>' + pulled_rows + '</tbody></table></div></section>') if prow_list else ''}
<script>{LB_JS}</script>
"""
    return page("Leaderboards", body, 0, "leaderboards")


def build(repo: Path, output: Path) -> int:
    solvers = collect(repo)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "style.css").write_text(CSS, encoding="utf-8")
    (output / "index.html").write_text(overview_page(solvers), encoding="utf-8")
    (output / "catalogue.html").write_text(index_page(solvers), encoding="utf-8")
    (output / "leaderboards.html").write_text(leaderboard_page(solvers), encoding="utf-8")
    (output / "missing.html").write_text(missing_page(solvers), encoding="utf-8")
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
