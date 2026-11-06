#!/usr/bin/env python3
"""Generate the interactive article charts.

    python3 scripts/article_charts.py [season] [out_dir]

Writes one self-contained page per chart into ``web/charts/`` (default), in
the board's hextech look: the same tokens, fonts, tooltip and entrance
motion as the Compare panel. Each page is meant to be embedded on its own
(a Notion HTML embed, an iframe in a post) and needs nothing but Google Fonts.

Every number comes from the season's ``standings.json`` and ``ledger.jsonl``
through the same loaders as ``analysis_report.py``; nothing is typed in.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_report import build_models, load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEASON = "s-2026-02+s-flash-probe+s-2026-07"
DEFAULT_OUT = ROOT / "web" / "charts"

FORFEIT_A = ("ABSTAIN_A", "FAILED_A", "FAULT_A")
FORFEIT_D = ("ABSTAIN_D", "FAILED_D")


def short_name(name: str) -> str:
    return name.replace("Claude ", "").replace(" Sol", "")


def role_record(ledger: list[dict], agent: str, theta: int, role: str) -> dict:
    """Played W-L and forfeits for one agent, one coin, one seat."""
    seat = "attacker" if role == "att" else "defender"
    rows = [r for r in ledger if r[seat] == agent and r["theta"] == theta]
    if role == "att":
        win, loss, forfeit = ("FN",) if theta else ("FP",), ("TP",) if theta else ("TN",), FORFEIT_A
    else:
        win, loss, forfeit = ("TP",) if theta else ("TN",), ("FN",) if theta else ("FP",), FORFEIT_D
    return {
        "w": sum(r["outcome"] in win for r in rows),
        "l": sum(r["outcome"] in loss for r in rows),
        "f": sum(r["outcome"] in forfeit for r in rows),
    }


def build_data(season: str) -> dict:
    standings, raw, ledger = load(season)
    models = build_models(standings, ledger)
    roster = {
        c["agent"]: c
        for c in json.loads((ROOT / "web" / "roster.json").read_text())["champions"]
    }

    out = []
    for m in models:
        row = m.row
        c = roster.get(m.name, {})
        ratings = {}
        for theta, tk in ((1, "theta1"), (0, "theta0")):
            for role, rk in (("all", ""), ("att", "att_"), ("def", "def_")):
                key = f"rating_{rk}{tk}"
                rec = (
                    {
                        k: role_record(ledger, m.name, theta, "att")[k]
                        + role_record(ledger, m.name, theta, "def")[k]
                        for k in ("w", "l", "f")
                    }
                    if role == "all"
                    else role_record(ledger, m.name, theta, role)
                )
                ratings[f"{tk}.{role}"] = {
                    "v": row.get(key),
                    "ci": row.get(f"{key}_ci"),
                    **rec,
                }
        out.append(
            {
                "agent": m.name,
                "name": short_name(c.get("name") or m.name),
                "model": row.get("model_name") or c.get("model") or "",
                "accent": c.get("accent") or "#C8AA6E",
                "glyph": c.get("glyph") or m.name[:2].upper(),
                "ratings": ratings,
                "def_elo": m.def_elo,
                "def_ci": m.def_ci,
                "cost": m.cost_per_round,
                "def_n": m.def_n,
                "tp": m.tp,
                "fn": m.fn,
                "fp": m.fp,
                "tn": m.tn,
                "defusal": m.defusal if m.tp + m.fn else None,
                "fpr": m.fpr if m.fp + m.tn else None,
                "fp_default": m.fp_default,
                "fp_real": m.fp_real,
                "attack_fn": m.attack_fn,
                "attack_tp": m.attack_tp,
                "fn_incomplete": m.fn_incomplete,
                "fn_smoke": m.fn_smoke,
                "fn_malformed": m.fn_malformed,
            }
        )
    clean = [r for r in ledger if r["theta"] == 0 and r["outcome"] in ("FP", "TN")]
    return {
        "season": season,
        "rounds": len(raw),
        "field_fpr": sum(r["outcome"] == "FP" for r in clean) / len(clean) if clean else 0,
        "clean_n": len(clean),
        "models": out,
    }


CHARTS = {
    "ratings": (
        "Ratings with 95% intervals",
        "Every model's rating with its 95% confidence interval. Switch the benchmark and the seat. "
        "Bars that overlap are a statistical tie.",
    ),
    "false-alarms": (
        "False alarms on clean code",
        "Share of clean services each model flagged as vulnerable while defending.",
    ),
    "audit-vs-price": (
        "Audit rating vs price",
        "Audit rating against what a round costs, log scale. The gold line is the Pareto frontier: "
        "nothing beats a model on it on both price and rating.",
    ),
    "catch-vs-noise": (
        "Catch vs noise",
        "Planted bugs fixed against false alarms on clean code. The shaded corner is the auditor to hire.",
    ),
    "attacks-survived": (
        "How attacks survived",
        "Every winning attack, split by why the defender's patch failed. None slipped past detection.",
    ),
}

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · Defuse Arena</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#010A13;--panel:#091428;--panel-2:#0F1B2D;--line:rgba(200,170,110,.16);--line-soft:rgba(200,170,110,.07);
--gold:#C8AA6E;--gold-2:#F0E6D2;--teal:#0AC8B9;--red:#E06060;--text:#CDBE91;--muted:#7A8CA3;
--font-display:"Cinzel","Iowan Old Style","Palatino Linotype",Georgia,serif;
--font-ui:"Rajdhani","Avenir Next","Segoe UI",system-ui,sans-serif;
--font-mono:"SFMono-Regular",ui-monospace,Menlo,monospace;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-ui);-webkit-font-smoothing:antialiased}
.card{margin:10px;padding:16px 18px 14px;border-radius:10px;position:relative;
background:linear-gradient(160deg,rgba(15,27,45,.95),rgba(6,16,31,.95));border:1px solid var(--line)}
.card::before{content:"";position:absolute;inset:5px;border-radius:7px;border:1px solid var(--line-soft);pointer-events:none}
.kicker{font-family:var(--font-display);font-size:9.5px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);opacity:.75}
h1{margin:4px 0 4px;font-family:var(--font-display);font-weight:700;font-size:17px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold-2)}
.sub{margin:0;color:var(--muted);font-size:13.5px;line-height:1.4;max-width:760px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 10px}
.seg{display:inline-flex;border:1px solid rgba(200,170,110,.24);border-radius:6px;overflow:hidden}
.chip{font-family:var(--font-display);font-size:10px;letter-spacing:.12em;text-transform:uppercase;padding:7px 12px;cursor:pointer;
color:var(--muted);background:rgba(200,170,110,.04);border:0;border-right:1px solid rgba(200,170,110,.16);transition:color .15s,background .15s}
.chip:last-child{border-right:0}
.chip:hover{color:var(--gold-2)}
.chip.on{color:var(--gold-2);background:linear-gradient(180deg,rgba(200,170,110,.18),rgba(200,170,110,.04));box-shadow:inset 0 -2px 0 var(--gold)}
.chip:focus-visible{outline:1px solid var(--teal);outline-offset:-1px}
.plot{border:1px solid rgba(200,170,110,.2);border-radius:8px;background:linear-gradient(180deg,rgba(1,10,19,.5),rgba(1,8,16,.78));overflow:hidden;margin-top:12px}
.plot svg{display:block;width:100%;height:auto}
.foot{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:9px;font-size:12px;color:var(--muted)}
.foot a{color:var(--gold);text-decoration:none}.foot a:hover{color:var(--gold-2)}
.legend{display:flex;gap:14px;flex-wrap:wrap}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.grid{stroke:rgba(200,170,110,.08)}
.tick{fill:var(--muted);font-family:var(--font-mono);font-size:9.5px}
.axis{fill:var(--muted);font-family:var(--font-display);font-size:9px;letter-spacing:.14em;text-transform:uppercase}
.name{fill:var(--gold-2);font-family:var(--font-ui);font-weight:600;font-size:13px}
@media (max-width:600px){.name{font-size:11.5px}.num{font-size:9.5px}}
.num{fill:var(--text);font-family:var(--font-mono);font-size:10.5px}
.num.dim,.name.dim{fill:var(--muted)}
.prior{stroke:rgba(200,170,110,.45);stroke-dasharray:4 4}
.priorl{fill:rgba(200,170,110,.7);font-family:var(--font-mono);font-size:9px}
.corner{fill:rgba(200,170,110,.5);font-family:var(--font-display);font-size:8.5px;letter-spacing:.14em;text-transform:uppercase}
.corner.best{fill:rgba(10,200,185,.8)}
.shade{fill:rgba(10,200,185,.06);stroke:rgba(10,200,185,.25);stroke-dasharray:3 3}
.cross{stroke:rgba(200,170,110,.22);stroke-dasharray:4 4}
.mark{cursor:pointer;outline:none;transition:opacity .2s}
svg.hovering .mark:not(.hot){opacity:.28}
.lbl{fill:var(--gold-2);font-family:var(--font-display);font-size:9.5px;letter-spacing:.04em;paint-order:stroke;stroke:rgba(1,8,16,.92);stroke-width:3px;stroke-linejoin:round;pointer-events:none}
.leader{stroke:rgba(240,230,210,.3);stroke-width:.7}
.guide line{stroke:rgba(10,200,185,.6);stroke-dasharray:3 3}
.guide rect{fill:rgba(1,10,19,.95);stroke:rgba(10,200,185,.6)}
.guide text{fill:var(--teal);font-family:var(--font-mono);font-size:9.5px}
.frontier{fill:none;stroke:var(--gold);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.frontier-glow{fill:none;stroke:rgba(200,170,110,.18);stroke-width:7;stroke-linecap:round;stroke-linejoin:round}
.pop{transition:transform .18s cubic-bezier(.2,.9,.25,1);animation:pop .55s cubic-bezier(.2,1.4,.4,1) backwards;animation-delay:calc(var(--i,0) * 40ms)}
.mark.hot .pop{transform:scale(1.25);transition:transform .18s cubic-bezier(.2,.9,.25,1)}
@keyframes pop{from{transform:scale(0);opacity:0}to{transform:scale(1);opacity:1}}
@media (prefers-reduced-motion:reduce){.pop{animation:none}}
.still .pop{animation:none}
.avg{stroke:var(--gold);stroke-dasharray:3 3;stroke-width:1.2}
.avgl{fill:var(--gold);font-family:var(--font-mono);font-size:9.5px}
#tip{position:fixed;z-index:9;max-width:300px;padding:11px 13px;pointer-events:none;opacity:0;transition:opacity .1s;
background:linear-gradient(180deg,#0B1B33,#071223);border:1px solid rgba(200,170,110,.45);border-radius:8px;
box-shadow:0 12px 34px rgba(0,0,0,.65),0 0 0 1px rgba(10,200,185,.08) inset;font-size:13px;line-height:1.45}
#tip b{display:block;font-family:var(--font-display);letter-spacing:.06em;color:var(--gold-2);font-size:11.5px;text-transform:uppercase;margin-bottom:5px}
#tip .v{color:var(--gold);font-family:var(--font-mono);font-size:12px}
#tip .m{color:var(--muted);font-size:12px}
#tip p{margin:0}
@media (max-width:560px){.card{margin:0;border-radius:0;padding:14px 12px}.chip{padding:7px 9px;font-size:9px}}
</style>
</head>
<body>
<div class="card">
  <div class="kicker">Defuse Arena · __ROUNDS__ rounds</div>
  <h1>__TITLE__</h1>
  <p class="sub">__SUB__</p>
  <div class="bar" id="bar"></div>
  <div class="plot" id="plot"></div>
  <div class="foot"><div class="legend" id="legend"></div><a href="https://defuse-arena.vercel.app" target="_blank" rel="noopener">defuse-arena.vercel.app ↗</a></div>
</div>
<div id="tip" role="tooltip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
const CHART = "__CHART__";
const D = JSON.parse(document.getElementById("data").textContent);
const M = D.models;
const NS = "http://www.w3.org/2000/svg";
const REDUCE = matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]static\b/.test(location.search);
if (REDUCE) document.documentElement.classList.add("still");
const C = { gold: "#C8AA6E", teal: "#0AC8B9", red: "#E06060", dim: "#1b2a40", gold2: "#F0E6D2" };
const plot = document.getElementById("plot"), bar = document.getElementById("bar"), legend = document.getElementById("legend");
const tip = document.getElementById("tip");

function el(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function txt(tag, attrs, text, parent) { const n = el(tag, attrs, parent); n.textContent = text; return n; }
const pct = v => v == null ? "—" : Math.round(v * 100) + "%";
const usd = v => "$" + (v < 0.1 ? v.toFixed(3) : v.toFixed(2));
const ease = t => 1 - Math.pow(1 - t, 3);
function tween(ms, delay, fn) {
  if (REDUCE) { fn(1); return; }
  const t0 = performance.now() + delay;
  const step = now => { const t = Math.min(1, Math.max(0, (now - t0) / ms)); fn(ease(t)); if (t < 1) requestAnimationFrame(step); };
  fn(0); requestAnimationFrame(step);
}
function showTip(ev, title, lines) {
  tip.textContent = "";
  const b = document.createElement("b"); b.textContent = title; tip.appendChild(b);
  for (const [cls, s] of lines) { const p = document.createElement("p"); p.className = cls; p.textContent = s; tip.appendChild(p); }
  tip.style.opacity = 1;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  const x = ev.clientX != null ? ev.clientX : ev.x, y = ev.clientY != null ? ev.clientY : ev.y;
  tip.style.left = Math.min(innerWidth - w - 8, Math.max(8, x + 14)) + "px";
  tip.style.top = (y - h - 14 < 8 ? y + 18 : y - h - 14) + "px";
}
function hideTip() { tip.style.opacity = 0; }
function hoverable(svg, node, onTip) {
  node.classList.add("mark");
  node.setAttribute("tabindex", "0");
  const on = ev => { svg.classList.add("hovering"); svg.querySelectorAll(".hot").forEach(n => n.classList.remove("hot")); node.classList.add("hot"); onTip(ev); };
  const off = () => { svg.classList.remove("hovering"); node.classList.remove("hot"); hideTip(); };
  node.addEventListener("pointermove", on);
  node.addEventListener("pointerleave", off);
  node.addEventListener("focus", () => { const r = node.getBoundingClientRect(); on({ x: r.left + r.width / 2, y: r.top }); });
  node.addEventListener("blur", off);
}
function addLegend(items) {
  legend.textContent = "";
  for (const [color, label] of items) {
    const s = document.createElement("span"); const i = document.createElement("i");
    i.style.background = color; s.appendChild(i); s.appendChild(document.createTextNode(label)); legend.appendChild(s);
  }
}
function segmented(options, value, onPick) {
  const seg = document.createElement("div"); seg.className = "seg"; seg.setAttribute("role", "group");
  for (const [k, label] of options) {
    const b = document.createElement("button"); b.className = "chip" + (k === value ? " on" : ""); b.textContent = label;
    b.setAttribute("aria-pressed", k === value ? "true" : "false");
    b.addEventListener("click", () => { seg.querySelectorAll(".chip").forEach(x => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); });
      b.classList.add("on"); b.setAttribute("aria-pressed", "true"); onPick(k); });
    seg.appendChild(b);
  }
  bar.appendChild(seg);
}
function width() { return Math.max(340, Math.min(980, plot.clientWidth || 900)); }

/* ---------------------------------------------------------- ratings */
function ratings() {
  const q = new URLSearchParams(location.search);
  const state = { theta: q.get("bench") === "control" ? "theta0" : "theta1",
    role: { overall: "all", attack: "att", defence: "def", defense: "def" }[q.get("seat")] || "def" };
  const ROLE = { all: ["Overall", C.gold], att: ["Attack", C.red], def: ["Defence", C.teal] };
  const SEAT = { theta1: { att: "red team", def: "audit" }, theta0: { att: "clean build", def: "audit" } };
  segmented([["theta1", "⚔ Vulnerability"], ["theta0", "○ Control"]], state.theta, k => { state.theta = k; update(); });
  segmented([["all", "Overall"], ["att", "Attack"], ["def", "Defence"]], state.role, k => { state.role = k; update(); });
  let lo = Infinity, hi = -Infinity;
  for (const m of M) for (const k in m.ratings) { const r = m.ratings[k]; if (r.v == null) continue; lo = Math.min(lo, r.v - r.ci); hi = Math.max(hi, r.v + r.ci); }
  lo = Math.floor(lo / 100) * 100; hi = Math.ceil(hi / 100) * 100;
  let svg, rows = new Map(), W, X, L, R, rowH, top;

  function build() {
    plot.textContent = ""; rows = new Map();
    W = width(); const narrow = W < 600;
    L = narrow ? 128 : 150; R = narrow ? 44 : 118; top = 30; rowH = narrow ? 27 : 30;
    const H = top + rowH * M.length + 34;
    svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Ratings with 95% intervals" }, plot);
    X = v => L + (v - lo) / (hi - lo) * (W - L - R);
    const step = narrow ? 200 : 100;
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      el("line", { class: "grid", x1: X(t), x2: X(t), y1: top - 6, y2: top + rowH * M.length }, svg);
      txt("text", { class: "tick", x: X(t), y: top + rowH * M.length + 16, "text-anchor": "middle" }, t, svg);
    }
    el("line", { class: "prior", x1: X(1500), x2: X(1500), y1: top - 12, y2: top + rowH * M.length }, svg);
    txt("text", { class: "priorl", x: X(1500) + 5, y: top - 14 }, "prior 1500", svg);
    txt("text", { class: "axis", x: L + (W - L - R) / 2, y: top + rowH * M.length + 31, "text-anchor": "middle" }, "rating · 95% interval", svg);
    M.forEach((m, i) => {
      const g = el("g", { "data-agent": m.agent }, svg);
      el("rect", { x: 0, y: -rowH / 2, width: W, height: rowH, fill: "transparent" }, g);
      el("path", { d: "M0,-4 L4,0 L0,4 L-4,0Z", transform: `translate(${L - 12 - (narrow ? 0 : 0)},0)`, fill: m.accent, opacity: .9 }, g);
      const name = txt("text", { class: "name", x: L - 22, y: 4, "text-anchor": "end" }, m.name, g);
      const band = el("rect", { y: -2.5, height: 5, rx: 2.5, opacity: .55 }, g);
      const capL = el("line", { y1: -6, y2: 6, "stroke-width": 1.5 }, g);
      const capR = el("line", { y1: -6, y2: 6, "stroke-width": 1.5 }, g);
      const dot = el("circle", { r: 5.2, stroke: "rgba(240,230,210,.9)", "stroke-width": 1.2 }, g);
      const num = txt("text", { class: "num", x: W - R + 10, y: 4 }, "", g);
      const row = { g, name, band, capL, capR, dot, num, cur: null, m };
      rows.set(m.agent, row);
      hoverable(svg, g, ev => {
        const r = m.ratings[`${state.theta}.${state.role}`];
        const seat = state.role === "all" ? "overall" : SEAT[state.theta][state.role];
        const lines = [["v", `${Math.round(r.v)}  ·  95% CI ${Math.round(r.v - r.ci)}–${Math.round(r.v + r.ci)}`],
          ["", `${state.theta === "theta1" ? "Vulnerability" : "Control"} · ${seat}`],
          ["", `Record ${r.w}–${r.l}` + (r.f ? ` · ${r.f} forfeited` : "")]];
        if (m.model) lines.push(["m", m.model]);
        showTip(ev, m.name, lines);
      });
    });
    update(true);
  }

  function update(first) {
    const key = `${state.theta}.${state.role}`;
    const color = ROLE[state.role][1];
    const order = M.slice().sort((a, b) => b.ratings[key].v - a.ratings[key].v);
    const narrow = W < 600;
    order.forEach((m, rank) => {
      const row = rows.get(m.agent), r = m.ratings[key];
      const played = r.w + r.l > 0;
      const to = { y: top + rowH * (rank + 0.5), v: r.v, lo: r.v - r.ci, hi: r.v + r.ci, o: played ? 1 : 0.38 };
      const from = row.cur || { y: to.y, v: 1500, lo: 1500, hi: 1500, o: 0 };
      row.dot.setAttribute("fill", color); row.band.setAttribute("fill", color);
      row.capL.setAttribute("stroke", color); row.capR.setAttribute("stroke", color);
      row.num.textContent = played ? (narrow ? `${Math.round(r.v)}` : `${Math.round(r.v)} ±${Math.round(r.ci)}`)
        : (narrow ? "—" : (r.f ? "refused all" : "no rounds"));
      row.num.classList.toggle("dim", !played); row.name.classList.toggle("dim", !played);
      tween(first ? 900 : 650, first ? rank * 45 : 0, t => {
        const c = k => from[k] + (to[k] - from[k]) * t;
        const y = c("y"), a = X(c("lo")), b = X(c("hi"));
        row.g.setAttribute("transform", `translate(0,${y.toFixed(1)})`);
        row.band.setAttribute("x", a); row.band.setAttribute("width", Math.max(0, b - a));
        row.capL.setAttribute("x1", a); row.capL.setAttribute("x2", a);
        row.capR.setAttribute("x1", b); row.capR.setAttribute("x2", b);
        row.dot.setAttribute("cx", X(c("v")));
        row.g.style.opacity = c("o");
      });
      row.cur = to;
    });
    addLegend([[color, `${ROLE[state.role][0]}${state.role === "all" ? "" : " · " + SEAT[state.theta][state.role]}`],
      ["rgba(200,170,110,.45)", "dashed = 1500 prior"], ["#3a475a", "dimmed = no played rounds"]]);
  }
  build();
  let rw; addEventListener("resize", () => { clearTimeout(rw); rw = setTimeout(() => { if (Math.abs(width() - W) > 40) build(); }, 150); });
}

/* ---------------------------------------------------------- stacked bars */
function stacked(spec) {
  let W0;
  function build() {
    plot.textContent = "";
    const W = width(); W0 = W; const narrow = W < 600;
    const rows = spec.rows();
    const L = narrow ? 128 : 140, R = narrow ? 44 : 150, top = 22, rowH = narrow ? 25 : 28;
    const H = top + rowH * rows.length + (spec.axis ? 34 : 14);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.label }, plot);
    const X = v => L + v / spec.max(rows) * (W - L - R);
    if (spec.axis) for (const t of spec.axis) {
      el("line", { class: "grid", x1: X(t), x2: X(t), y1: top - 4, y2: top + rowH * rows.length }, svg);
      txt("text", { class: "tick", x: X(t), y: top + rowH * rows.length + 15, "text-anchor": "middle" }, spec.tick(t), svg);
    }
    rows.forEach((r, i) => {
      const y = top + rowH * (i + 0.5);
      const g = el("g", { transform: `translate(0,${y})` }, svg);
      el("rect", { x: 0, y: -rowH / 2, width: W, height: rowH, fill: "transparent" }, g);
      el("path", { d: "M0,-4 L4,0 L0,4 L-4,0Z", transform: `translate(${L - 12},0)`, fill: r.m.accent, opacity: .9 }, g);
      txt("text", { class: "name", x: L - 22, y: 4, "text-anchor": "end" }, r.m.name, g);
      let acc = 0; const segs = [];
      r.parts.forEach(([v, color]) => { if (v > 0) segs.push([acc, v, color]); acc += v; });
      const h = rowH * 0.56;
      segs.forEach(([start, v, color], j) => {
        const x0 = X(start), w = X(start + v) - X(start);
        const rect = el("rect", { x: x0, y: -h / 2, height: h, width: 0, rx: 3, fill: color }, g);
        tween(700, i * 45 + j * 120, t => rect.setAttribute("width", Math.max(0, w * t - (j < segs.length - 1 ? 2 : 0))));
      });
      txt("text", { class: "num", x: (spec.labelAtBar ? X(acc) + 8 : W - R + 10), y: 4 }, narrow ? r.short : r.label, g);
      hoverable(svg, g, ev => showTip(ev, r.m.name, r.tip));
    });
    if (spec.avg != null) {
      const x = X(spec.avg);
      const line = el("line", { class: "avg", x1: x, x2: x, y1: top - 8, y2: top + rowH * rows.length }, svg);
      const label = txt("text", { class: "avgl", x: x + 5, y: top - 10 }, spec.avgLabel, svg);
      line.style.opacity = 0; label.style.opacity = 0;
      tween(500, rows.length * 45 + 300, t => { line.style.opacity = t; label.style.opacity = t; });
    }
    addLegend(spec.legend);
  }
  build();
  let rw; addEventListener("resize", () => { clearTimeout(rw); rw = setTimeout(() => { if (Math.abs(width() - W0) > 40) build(); }, 150); });
}

/* ---------------------------------------------------------- scatter */
function scatter(spec) {
  let W0;
  function build() {
    plot.textContent = "";
    const W = width(); W0 = W; const narrow = W < 600;
    const H = Math.round(W * (narrow ? 0.9 : 0.56));
    const L = 58, R = 22, T = 18, B = 48;
    const pts = spec.points();
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.label }, plot);
    const X = spec.x.log
      ? v => L + (Math.log(v) - Math.log(spec.x.min)) / (Math.log(spec.x.max) - Math.log(spec.x.min)) * (W - L - R)
      : v => L + (v - spec.x.min) / (spec.x.max - spec.x.min) * (W - L - R);
    const Y = v => T + (1 - (v - spec.y.min) / (spec.y.max - spec.y.min)) * (H - T - B);
    if (spec.shade) {
      const [x0, y0, x1, y1] = spec.shade;
      const s = el("rect", { class: "shade", x: X(x0), y: Y(y1), width: X(x1) - X(x0), height: Y(y0) - Y(y1), rx: 4 }, svg);
      s.style.opacity = 0; tween(800, 100, t => s.style.opacity = t);
    }
    for (const t of spec.x.ticks) {
      el("line", { class: "grid", x1: X(t), x2: X(t), y1: T, y2: H - B }, svg);
      txt("text", { class: "tick", x: X(t), y: H - B + 15, "text-anchor": "middle" }, spec.x.fmt(t), svg);
    }
    for (const t of spec.y.ticks) {
      el("line", { class: "grid", x1: L, x2: W - R, y1: Y(t), y2: Y(t) }, svg);
      txt("text", { class: "tick", x: L - 7, y: Y(t) + 3, "text-anchor": "end" }, spec.y.fmt(t), svg);
    }
    txt("text", { class: "axis", x: L + (W - L - R) / 2, y: H - 12, "text-anchor": "middle" }, spec.x.title, svg);
    txt("text", { class: "axis", x: 14, y: T + (H - T - B) / 2, "text-anchor": "middle", transform: `rotate(-90 14 ${T + (H - T - B) / 2})` }, spec.y.title, svg);
    const boxes = pts.map(p => ({ x0: X(p.x) - p.r, x1: X(p.x) + p.r, y0: Y(p.y) - p.r, y1: Y(p.y) + p.r }));
    if (spec.corners) for (const [cx, cy, anchor, label, best] of spec.corners) {
      let x = cx < 0.5 ? L + 8 : W - R - 8, y = cy < 0.5 ? H - B - 8 : T + 14, a = cx < 0.5 ? "start" : "end";
      if (best && spec.shade) { x = X(spec.shade[0]) + 8; y = Y(spec.shade[1]) - 7; a = "start"; }
      const n = txt("text", { class: "corner" + (best ? " best" : ""), x, y, "text-anchor": a }, label, svg);
      const w = label.length * 6.6;
      boxes.push({ x0: a === "start" ? x : x - w, x1: a === "start" ? x + w : x, y0: y - 9, y1: y + 2 });
      n.style.opacity = 0; tween(600, 300, t => n.style.opacity = t);
    }
    if (spec.frontier) {
      const f = spec.frontier(pts);
      if (f.length > 1) {
        const d = f.map((p, i) => (i ? "L" : "M") + X(p.x).toFixed(1) + "," + Y(p.y).toFixed(1)).join("");
        const glow = el("path", { class: "frontier-glow", d }, svg);
        const path = el("path", { class: "frontier", d }, svg);
        const len = path.getTotalLength();
        for (let d = 0; d <= len; d += 5) { const q = path.getPointAtLength(d); boxes.push({ x0: q.x - 3, x1: q.x + 3, y0: q.y - 3, y1: q.y + 3 }); }
        path.style.strokeDasharray = len; glow.style.opacity = 0;
        tween(1100, 450, t => { path.style.strokeDashoffset = len * (1 - t); glow.style.opacity = t; });
      }
    }
    const guide = el("g", { class: "guide" }, svg); guide.style.display = "none";
    const gx = el("line", {}, guide), gy = el("line", {}, guide);
    const bx = el("rect", { rx: 3, height: 15 }, guide), by = el("rect", { rx: 3, height: 15 }, guide);
    const tx = txt("text", { "text-anchor": "middle" }, "", guide), ty = txt("text", { "text-anchor": "end" }, "", guide);
    function showGuide(p) {
      const x = X(p.x), y = Y(p.y);
      guide.style.display = "";
      gx.setAttribute("x1", x); gx.setAttribute("x2", x); gx.setAttribute("y1", y); gx.setAttribute("y2", H - B);
      gy.setAttribute("x1", L); gy.setAttribute("x2", x); gy.setAttribute("y1", y); gy.setAttribute("y2", y);
      tx.textContent = spec.x.fmt(p.x, true); ty.textContent = spec.y.fmt(p.y, true);
      const wx = tx.textContent.length * 6 + 10, wy = ty.textContent.length * 6 + 10;
      bx.setAttribute("x", x - wx / 2); bx.setAttribute("y", H - B + 2); bx.setAttribute("width", wx);
      tx.setAttribute("x", x); tx.setAttribute("y", H - B + 13);
      by.setAttribute("x", L - wy - 2); by.setAttribute("y", y - 8); by.setAttribute("width", wy);
      ty.setAttribute("x", L - 7); ty.setAttribute("y", y + 3.5);
    }
    // label placement: greedy, around the dot, avoiding dots and earlier labels
    const hit = b => boxes.some(o => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0)
      || b.x0 < L + 2 || b.x1 > W - R - 2 || b.y0 < T + 2 || b.y1 > H - B - 2;
    const order = pts.map((p, i) => i).sort((a, b) => pts[b].r - pts[a].r);
    const place = {};
    for (const i of order) {
      const p = pts[i], x = X(p.x), y = Y(p.y), w = p.label.length * 6.4 + 4, h = 12, r = p.r + 5;
      const tries = [];
      for (const k of [1, 1.9, 2.9, 4]) tries.push([x + r * k, y + 3.5, "start"], [x - r * k, y + 3.5, "end"],
        [x, y - r * k, "middle"], [x, y + r * k + 9, "middle"], [x + r * k * .8, y - r * k * .8, "start"], [x - r * k * .8, y - r * k * .8, "end"],
        [x + r * k * .8, y + r * k * .8 + 6, "start"], [x - r * k * .8, y + r * k * .8 + 6, "end"]);
      let pick = tries[0];
      for (const t of tries) {
        const [lx, ly, a] = t, x0 = a === "start" ? lx : a === "end" ? lx - w : lx - w / 2;
        const b = { x0, x1: x0 + w, y0: ly - 10, y1: ly + 2 };
        if (!hit(b)) { pick = t; boxes.push(b); break; }
      }
      place[i] = pick;
    }
    pts.forEach((p, i) => {
      const x = X(p.x), y = Y(p.y);
      const g = el("g", {}, svg);
      const [lx, ly, a] = place[i];
      if (Math.hypot(lx - x, ly - 3.5 - y) > p.r + 16) el("line", { class: "leader", x1: x, y1: y, x2: lx, y2: ly - 3.5 }, g);
      const mark = el("g", { transform: `translate(${x},${y})` }, g);
      const inner = el("g", {}, mark);
      el("circle", { r: Math.max(18, p.r + 6), fill: "transparent" }, inner);
      el("circle", { r: p.r + 5, fill: p.color, opacity: .18 }, inner);
      el("circle", { r: p.r, fill: p.color, stroke: "rgba(240,230,210,.9)", "stroke-width": 1.2 }, inner);
      const lbl = txt("text", { class: "lbl", x: lx, y: ly, "text-anchor": a }, p.label, g);
      lbl.style.opacity = 0;
      inner.classList.add("pop"); inner.style.setProperty("--i", i);
      tween(500, i * 40 + 250, t => lbl.style.opacity = t);
      hoverable(svg, g, ev => { showGuide(p); showTip(ev, p.m.name, p.tip); });
      g.addEventListener("pointerleave", () => guide.style.display = "none");
      g.addEventListener("blur", () => guide.style.display = "none");
    });
    svg.appendChild(guide);
    addLegend(spec.legend);
  }
  build();
  let rw; addEventListener("resize", () => { clearTimeout(rw); rw = setTimeout(() => { if (Math.abs(width() - W0) > 40) build(); }, 150); });
}

/* ---------------------------------------------------------- the five charts */
const CHARTS = {
  "ratings": ratings,
  "false-alarms": () => stacked({
    label: "False alarms on clean code",
    rows: () => M.filter(m => m.fpr != null).sort((a, b) => b.fpr - a.fpr || a.name.localeCompare(b.name)).map(m => ({
      m, parts: [[m.fp_default / (m.fp + m.tn), C.gold], [m.fp_real / (m.fp + m.tn), C.red], [m.tn / (m.fp + m.tn), C.dim]],
      label: `${pct(m.fpr)}  ·  ${m.fp} of ${m.fp + m.tn}`, short: pct(m.fpr),
      tip: [["v", `${pct(m.fpr)} false alarms`], ["", `${m.fp} of ${m.fp + m.tn} clean services flagged`],
        ["m", `${m.fp_default} on the default admin token · ${m.fp_real} other`]] })),
    max: () => 1, axis: [0, .25, .5, .75, 1], tick: pct,
    avg: D.field_fpr, avgLabel: `field ${pct(D.field_fpr)}`,
    legend: [[C.gold, "flagged the default admin token"], [C.red, "flagged something else"], [C.dim, "cleared"]],
  }),
  "attacks-survived": () => stacked({
    label: "How attacks survived",
    rows: () => M.filter(m => m.attack_fn > 0).sort((a, b) => b.attack_fn - a.attack_fn).map(m => ({
      m, parts: [[m.fn_incomplete, C.teal], [m.fn_smoke, C.gold], [m.fn_malformed, C.red]],
      label: `${m.attack_fn} of ${m.attack_fn + m.attack_tp} survived`, short: `${m.attack_fn}/${m.attack_fn + m.attack_tp}`,
      tip: [["v", `${m.attack_fn} of ${m.attack_fn + m.attack_tp} played attacks survived`],
        ["", `${m.fn_incomplete} incomplete fix · ${m.fn_smoke} patch broke the service · ${m.fn_malformed} patch did not apply`],
        ["m", "Every one was detected; the fix failed"]] })),
    max: rows => Math.max(...rows.map(r => r.m.attack_fn)), labelAtBar: true,
    legend: [[C.teal, "fix incomplete — exploit still works"], [C.gold, "fix broke the service"], [C.red, "patch did not apply"]],
  }),
  "audit-vs-price": () => scatter({
    label: "Audit rating vs price",
    points: () => M.filter(m => m.cost > 0).map(m => ({ m, x: m.cost, y: m.def_elo, r: 4 + Math.sqrt(m.def_n) * 1.1, color: m.accent, label: m.name,
      tip: [["v", `Audit ${Math.round(m.def_elo)} ±${Math.round(m.def_ci)}  ·  ${usd(m.cost)} per round`], ["", `${m.def_n} played audit rounds`], ["m", m.model]] })),
    x: { log: true, min: 0.03, max: 1.2, ticks: [0.03, 0.05, 0.1, 0.25, 0.5, 1], fmt: v => usd(v), title: "$ per round · log scale" },
    y: { min: 1200, max: 1750, ticks: [1200, 1300, 1400, 1500, 1600, 1700], fmt: v => Math.round(v), title: "audit rating" },
    frontier: pts => { const s = pts.slice().sort((a, b) => a.x - b.x); const f = []; let best = -Infinity; for (const p of s) if (p.y > best) { f.push(p); best = p.y; } return f; },
    corners: [[0, 1, "start", "cheap and strong", true], [1, 1, "end", "strong but pricey"], [0, 0, "start", "cheap but weak"], [1, 0, "end", "pricey and weak"]],
    legend: [[C.gold, "Pareto frontier"], ["#7A8CA3", "bubble = audit rounds played"]],
  }),
  "catch-vs-noise": () => scatter({
    label: "Catch vs noise",
    points: () => M.filter(m => m.defusal != null && m.fpr != null).map(m => ({ m, x: m.fpr, y: m.defusal, r: 4 + Math.sqrt(m.def_n) * 1.1, color: m.accent, label: m.name,
      tip: [["v", `Fixed ${m.tp} of ${m.tp + m.fn} planted bugs  ·  ${pct(m.fpr)} false alarms`], ["", `${m.fp} of ${m.fp + m.tn} clean services flagged`], ["m", m.model]] })),
    x: { min: 0, max: 1, ticks: [0, .2, .4, .6, .8, 1], fmt: pct, title: "false alarms on clean code" },
    y: { min: 0.3, max: 1.06, ticks: [.4, .6, .8, 1], fmt: pct, title: "planted bugs fixed" },
    shade: [0, 0.85, 0.25, 1.06],
    corners: [[0, 1, "start", "the auditor to hire", true], [1, 1, "end", "alarmist"], [0, 0, "start", "quiet but blind"], [1, 0, "end", "noisy and blind"]],
    legend: [["rgba(10,200,185,.5)", "shaded = fixes bugs, stays quiet on clean code"], ["#7A8CA3", "bubble = audit rounds played"]],
  }),
};
CHARTS[CHART]();
</script>
</body>
</html>
"""


def main() -> None:
    season = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEASON
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_data(season)
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    for chart, (title, sub) in CHARTS.items():
        page = (
            PAGE.replace("__TITLE__", title)
            .replace("__SUB__", sub)
            .replace("__ROUNDS__", str(data["rounds"]))
            .replace("__CHART__", chart)
            .replace("__DATA__", blob)
        )
        path = out_dir / f"{chart}.html"
        path.write_text(page)
        print(f"{path}: {len(page) // 1024} KB")


if __name__ == "__main__":
    main()
