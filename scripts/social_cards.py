#!/usr/bin/env python3
"""Generate the launch-thread chart videos: one title and one chart each.

    python3 scripts/social_cards.py [season] [out_dir]

Writes one HyperFrames project per card into ``article/social/<slug>/``
(1920x1080, 30 fps, ~6.5 s), in the board's hextech look. Render each with

    cd article/social/<slug> && npx hyperframes render

Every number comes from the season's ``standings.json`` and ``ledger.jsonl``
through the same loaders as ``article_charts.py``; nothing is typed in except
the wording around the numbers.
"""
from __future__ import annotations

import html
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_report import load  # noqa: E402
from article_charts import DEFAULT_SEASON, build_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "article" / "social"
FONTS = ROOT / "article" / "social" / "_fonts"
SITE = "defuse-arena.vercel.app"
W, H = 1920, 1080
DUR = 8

GOLD, GOLD2, TEAL, RED, ORANGE, MUTED, TEXT = (
    "#C8AA6E", "#F0E6D2", "#0AC8B9", "#E06060", "#E8A24A", "#7A8CA3", "#CDBE91",
)
GREY = "rgba(122,140,163,.55)"
LABEL_GREY = "#A3B1C2"  # value text beside a grey bar: 3:1 or better on the ground


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


# --------------------------------------------------------------------------
# data


def season_data(season: str) -> dict:
    d = build_data(season)
    standings, _, ledger = load(season)
    net = {r["agent"]: r.get("net_chips") or 0.0 for r in standings["rows"]}
    by_agent = {m["agent"]: m for m in d["models"]}
    for a, m in by_agent.items():
        rows = [r for r in ledger if r["attacker"] == a and r["theta"] == 1]
        m["att_rounds"] = len(rows)
        m["att_refused"] = sum(r["outcome"] == "ABSTAIN_A" for r in rows)
        m["net"] = net.get(a, 0.0)
    played1 = [r for r in ledger if r["theta"] == 1 and r["outcome"] in ("TP", "FN")]
    d["planted"] = len(played1)
    d["survived"] = sum(r["outcome"] == "FN" for r in played1)
    d["fn_reasons"] = {
        "incomplete": sum(m["fn_incomplete"] for m in d["models"]),
        "smoke": sum(m["fn_smoke"] for m in d["models"]),
        "malformed": sum(m["fn_malformed"] for m in d["models"]),
    }
    d["ledger"] = ledger
    d["refused"] = sum(r["outcome"] in ("ABSTAIN_A", "ABSTAIN_D") for r in ledger)
    d["vuln_played"] = sum(r["theta"] == 1 and r["outcome"] in ("TP", "FN") for r in ledger)
    d["clean_tn"] = sum(r["theta"] == 0 and r["outcome"] == "TN" for r in ledger)
    d["clean_fp"] = sum(r["theta"] == 0 and r["outcome"] == "FP" for r in ledger)
    return d


# --------------------------------------------------------------------------
# shared bar rows: [(label, sub, value 0..1, value_text, color)]


def bar_rows(rows, *, x0=430, x1=1640, y0=0, row_h=48, bar_h=26, ref=None, ref_label=""):
    """SVG for a horizontal bar list. Bars carry ids bar-i, labels val-i."""
    span = x1 - x0
    out = []
    height = len(rows) * row_h
    for g in (0, 0.25, 0.5, 0.75, 1):
        x = x0 + span * g
        out.append(f'<line class="grid" x1="{x:.1f}" y1="{y0 - 14}" x2="{x:.1f}" y2="{y0 + height}"/>')
        out.append(f'<text class="tick" x="{x:.1f}" y="{y0 + height + 30}" text-anchor="middle">{round(g * 100)}%</text>')
    for i, (label, sub, v, vt, color) in enumerate(rows):
        y = y0 + i * row_h
        cy = y + row_h / 2
        w = max(span * v, 4)
        out.append(
            f'<g id="row-{i}" class="row">'
            f'<text class="name" x="{x0 - 22}" y="{cy + 2}" text-anchor="end" dominant-baseline="middle">{esc(label)}'
            + (f'<tspan class="sub" dx="10">{esc(sub)}</tspan>' if sub else "")
            + "</text>"
            f'<rect class="track" x="{x0}" y="{cy - bar_h / 2}" width="{span}" height="{bar_h}" rx="3"/>'
            f'<rect id="bar-{i}" class="bar" x="{x0}" y="{cy - bar_h / 2}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{color}"/>'
            f'<text id="val-{i}" class="val" x="{x0 + w + 14:.1f}" y="{cy + 2}" dominant-baseline="middle" fill="{LABEL_GREY if color.startswith("rgba") else color}">{esc(vt)}</text>'
            "</g>"
        )
    if ref is not None:
        x = x0 + span * ref
        out.append(
            f'<g id="ref"><line class="ref" x1="{x:.1f}" y1="{y0 - 30}" x2="{x:.1f}" y2="{y0 + height + 6}"/>'
            f'<text class="refl" x="{x + 10:.1f}" y="{y0 - 18}">{esc(ref_label)}</text></g>'
        )
    return "\n".join(out), height


REF_SCRIPT = """
tl.fromTo("#ref", {opacity:0}, {opacity:1, duration:.4, ease:"power2.out"}, .9);"""

BAR_SCRIPT = """
tl.fromTo(".row", {opacity:0, x:-18}, {opacity:1, x:0, duration:.35, ease:"power3.out", stagger:.05}, .7);
tl.fromTo(".bar", {scaleX:0}, {scaleX:1, duration:.9, ease:"power3.out", stagger:.07, transformOrigin:"left center"}, 1.1);
tl.fromTo(".val", {opacity:0}, {opacity:1, duration:.3, stagger:.07}, 1.6);
"""


# --------------------------------------------------------------------------
# cards


def card_hero(d):
    """Every clean round as a square, in the order played; false alarms flip red."""
    clean = [r for r in d["ledger"] if r["theta"] == 0 and r["outcome"] in ("FP", "TN")]
    n, fp = len(clean), sum(r["outcome"] == "FP" for r in clean)
    cols, size, gap = 18, 50, 9
    gx = 640
    cells = []
    for i, r in enumerate(clean):
        row, c = divmod(i, cols)
        cls = "cell" + (" fp" if r["outcome"] == "FP" else "")
        cells.append(f'<rect class="{cls}" x="{gx + c * (size + gap)}" y="{20 + row * (size + gap)}" width="{size}" height="{size}" rx="6"/>')
    rows_n = math.ceil(n / cols)
    gh = 20 + rows_n * (size + gap)
    big = (
        f'<g id="big"><text id="bignum" class="bignum" x="0" y="250">{pct(fp / n)}</text>'
        f'<text class="bigl" x="6" y="320">of clean code</text>'
        f'<text class="bigl" x="6" y="362">flagged as hacked</text></g>'
        f'<g id="legend">'
        f'<rect x="{gx}" y="{gh + 30}" width="26" height="26" rx="5" fill="{TEAL}"/>'
        f'<text class="leg" x="{gx + 40}" y="{gh + 52}">{n - fp} clean, passed</text>'
        f'<rect x="{gx + 360}" y="{gh + 30}" width="26" height="26" rx="5" fill="{RED}"/>'
        f'<text class="leg" x="{gx + 400}" y="{gh + 52}">{fp} false alarms</text></g>'
    )
    target = round(fp / n * 100)
    return {
        "slug": "01-false-alarms",
        "kicker": "Control mode · defender seat",
        "title": f'We gave AI auditors clean code. They cried “hacked” <em class="hot">{pct(fp / n)}</em> of the time.',
        "sub": f"{n} services with nothing planted, audited by {len(d['models'])} models. Each square is one clean round, in the order played.",
        "svg": "\n".join(cells) + big,
        "svg_h": gh + 80,
        "note": "False alarm: the auditor reported an exploit that does not exist.",
        "script": f"""
tl.fromTo(".cell", {{opacity:0, scale:.4}}, {{opacity:1, scale:1, duration:.35, ease:"back.out(2)", stagger:.008, transformOrigin:"50% 50%"}}, .8);
tl.to(".cell.fp", {{fill:"{RED}", duration:.3, stagger:.03}}, 2.3);
tl.fromTo("#big", {{opacity:0, x:-16}}, {{opacity:1, x:0, duration:.4, ease:"power3.out"}}, 2.2);
const count = {{v: 0}};
tl.fromTo(count, {{v: 0}}, {{v: {target}, duration: {fp * 0.03 + 0.3:.2f}, ease: "none",
  onUpdate: () => {{ document.querySelector("#bignum").textContent = Math.round(count.v) + "%"; }} }}, 2.3);
tl.fromTo("#legend", {{opacity:0}}, {{opacity:1, duration:.4}}, 3.8);
""",
        "callout": "",
    }


def card_hero_combo(d):
    """01 and 04 in one film: the clean-round waffle, then the same space becomes the per-model bars."""
    clean = [r for r in d["ledger"] if r["theta"] == 0 and r["outcome"] in ("FP", "TN")]
    n, fp = len(clean), sum(r["outcome"] == "FP" for r in clean)
    cols, size, gap, gx = 18, 50, 9, 640
    cells = []
    for i, r in enumerate(clean):
        row, c = divmod(i, cols)
        cls = "cell" + (" fp" if r["outcome"] == "FP" else "")
        cells.append(f'<rect class="{cls}" x="{gx + c * (size + gap)}" y="{20 + row * (size + gap)}" width="{size}" height="{size}" rx="6"/>')
    gh = 20 + math.ceil(n / cols) * (size + gap)
    legend = (
        f'<g id="legend">'
        f'<rect x="{gx}" y="{gh + 30}" width="26" height="26" rx="5" fill="{TEAL}"/>'
        f'<text class="leg" x="{gx + 40}" y="{gh + 52}">{n - fp} clean, passed</text>'
        f'<rect x="{gx + 360}" y="{gh + 30}" width="26" height="26" rx="5" fill="{RED}"/>'
        f'<text class="leg" x="{gx + 400}" y="{gh + 52}">{fp} false alarms</text></g>'
    )
    big = (
        f'<g id="big"><text id="bignum" class="bignum" x="0" y="250">{pct(fp / n)}</text>'
        f'<text class="bigl" x="6" y="320">of clean code</text>'
        f'<text class="bigl" x="6" y="362">flagged as hacked</text>'
        f'<text class="bigs" x="6" y="420">{fp} of {n} clean rounds</text></g>'
    )
    ms = sorted([m for m in d["models"] if m["fpr"] is not None], key=lambda m: m["fpr"])
    rows = []
    for m in ms:
        f = m["fpr"]
        color = TEAL if f == 0 else RED if f >= 0.7 else GREY
        rows.append((m["name"], "", f, f'{pct(f)}  ({m["fp"]}/{m["fp"] + m["tn"]})', color))
    bars, bh = bar_rows(rows, x0=920, x1=1560, y0=40, row_h=37, bar_h=21,
                        ref=d["field_fpr"], ref_label=f'field average · {pct(d["field_fpr"])}')
    target = round(fp / n * 100)
    return {
        "slug": "01-alt-false-alarms",
        "dur": 12,
        "kicker": "Control mode · false alarms",
        "title": f'We gave AI auditors clean code. They cried “hacked” <em class="hot">{pct(fp / n)}</em> of the time.',
        "sub": f"{n} services with nothing planted, audited by {len(d['models'])} models. Each square is one clean round, in the order played.",
        "sub2": f"Who cries wolf: from {pct(ms[0]['fpr'])} for {ms[0]['name']} to {pct(ms[-1]['fpr'])} for {ms[-1]['name']}.",
        "svg": big + f'<g id="waffle">{"".join(cells)}{legend}</g><g id="bars">{bars}</g>',
        "svg_h": max(gh + 80, bh + 80),
        "note": "False alarm: the auditor reported an exploit that does not exist.",
        "script": f"""
tl.fromTo(".cell", {{opacity:0, scale:.4}}, {{opacity:1, scale:1, duration:.35, ease:"back.out(2)", stagger:.008, transformOrigin:"50% 50%"}}, .8);
tl.to(".cell.fp", {{fill:"{RED}", duration:.3, stagger:.03}}, 2.3);
tl.fromTo("#big", {{opacity:0, x:-16}}, {{opacity:1, x:0, duration:.4, ease:"power3.out"}}, 2.2);
const count = {{v: 0}};
tl.fromTo(count, {{v: 0}}, {{v: {target}, duration: {fp * 0.03 + 0.3:.2f}, ease: "none",
  onUpdate: () => {{ document.querySelector("#bignum").textContent = Math.round(count.v) + "%"; }} }}, 2.3);
tl.fromTo("#legend", {{opacity:0}}, {{opacity:1, duration:.4}}, 3.8);
tl.to("#waffle", {{opacity:0, y:-14, duration:.5, ease:"power2.in"}}, 5.4);
tl.to("#sub", {{opacity:0, duration:.35}}, 5.4);
tl.fromTo("#sub2", {{opacity:0, y:10}}, {{opacity:1, y:0, duration:.45, ease:"power3.out"}}, 5.8);
tl.fromTo("#bars", {{opacity:0}}, {{opacity:1, duration:.3}}, 5.8);
tl.fromTo("#bars .row", {{opacity:0, x:-18}}, {{opacity:1, x:0, duration:.35, ease:"power3.out", stagger:.05}}, 5.9);
tl.fromTo("#ref", {{opacity:0}}, {{opacity:1, duration:.4, ease:"power2.out"}}, 6.1);
tl.fromTo("#bars .bar", {{scaleX:0}}, {{scaleX:1, duration:.9, ease:"power3.out", stagger:.07, transformOrigin:"left center"}}, 6.3);
tl.fromTo("#bars .val", {{opacity:0}}, {{opacity:1, duration:.3, stagger:.07}}, 6.8);
""",
        "callout": "",
    }


def card_refusals(d):
    ms = sorted(d["models"], key=lambda m: (-m["att_refused"] / max(m["att_rounds"], 1), -m["att_rounds"]))
    refusers = [m for m in ms if m["att_refused"]]
    rest = [m for m in ms if not m["att_refused"] and m["att_rounds"]]
    rows = []
    for m in refusers:
        share = m["att_refused"] / m["att_rounds"]
        rows.append((m["name"], "", share, f'{m["att_refused"]} of {m["att_rounds"]} refused', RED if share == 1 else GOLD))
    rest_n = sum(m["att_rounds"] for m in rest)
    rows.append((f"{len(rest)} other models", "", 0, f"0 of {rest_n} refused", TEAL))
    svg, h = bar_rows(rows, y0=60, row_h=74, bar_h=34)
    full = [m for m in refusers if m["att_refused"] == m["att_rounds"]]
    full_n = sum(m["att_rounds"] for m in full)
    note = ", ".join(sorted(m["name"] for m in rest))
    return {
        "slug": "07-refusals",
        "kicker": "Vulnerability mode · attacker seat",
        "title": f'{len(full)} frontier models refused <em>every single</em> attack',
        "sub": f"Asked to plant a test backdoor for another model to catch, Claude and OpenAI models said no {full_n} times out of {full_n}.",
        "svg": svg,
        "svg_h": h + 120,
        "note": f"Did not refuse once: {note}.",
        "script": BAR_SCRIPT
        + 'tl.fromTo("#callout", {opacity:0, y:10}, {opacity:1, y:0, duration:.45, ease:"power3.out"}, 3.2);',
        "callout": f'<div id="callout" class="callout red">{full_n} / {full_n}<small>refused</small></div>',
    }


def card_false_alarms(d):
    ms = sorted([m for m in d["models"] if m["fpr"] is not None], key=lambda m: m["fpr"])
    rows = []
    for m in ms:
        f = m["fpr"]
        color = TEAL if f == 0 else RED if f >= 0.7 else GREY
        rows.append((m["name"], "", f, f'{pct(f)}  ({m["fp"]}/{m["fp"] + m["tn"]})', color))
    svg, h = bar_rows(rows, y0=50, row_h=42, bar_h=24, ref=d["field_fpr"], ref_label=f'field average · {pct(d["field_fpr"])}')
    return {
        "slug": "04-who-cries-wolf",
        "kicker": "Control mode · false alarms by model",
        "title": f'Who cries wolf: from <em>{pct(ms[0]["fpr"])}</em> to <em class="hot">{pct(ms[-1]["fpr"])}</em> false alarms',
        "sub": f'Share of clean services each model flagged as exploitable, out of {d["clean_n"]} clean rounds in total.',
        "svg": svg,
        "svg_h": h + 90,
        "chart_top": 300,
        "note": "Teal: zero false alarms. Red: flags most clean code.",
        "script": REF_SCRIPT + BAR_SCRIPT,
        "callout": "",
    }


def card_patch(d):
    n, s, rs = d["planted"], d["survived"], d["fn_reasons"]
    cols, size, gap = 24, 54, 12
    # survivors sit at the end of the grid so the flip reads left to right
    kinds = ["ok"] * (n - s) + ["inc"] * rs["incomplete"] + ["smoke"] * rs["smoke"] + ["mal"] * rs["malformed"]
    rows_n = math.ceil(n / cols)
    gw = cols * size + (cols - 1) * gap
    x0 = (W - 2 * 110 - gw) / 2
    cells = []
    for i, k in enumerate(kinds):
        r, c = divmod(i, cols)
        x, y = x0 + c * (size + gap), 40 + r * (size + gap)
        cls = "cell" + ("" if k == "ok" else f" fn {k}")
        cells.append(f'<rect class="{cls}" x="{x:.1f}" y="{y}" width="{size}" height="{size}" rx="6"/>')
    gh = rows_n * (size + gap)
    legend_y = 40 + gh + 70
    legend = (
        f'<g id="legend">'
        f'<rect x="{x0}" y="{legend_y - 22}" width="26" height="26" rx="5" fill="{TEAL}"/>'
        f'<text class="leg" x="{x0 + 40}" y="{legend_y}">{n - s} found and fixed</text>'
        f'<g id="leg-fn">'
        f'<rect x="{x0 + 470}" y="{legend_y - 22}" width="26" height="26" rx="5" fill="{RED}"/>'
        f'<text class="leg" x="{x0 + 510}" y="{legend_y}">{rs["incomplete"]} patch didn’t stop the exploit</text>'
        f'<rect x="{x0 + 1010}" y="{legend_y - 22}" width="26" height="26" rx="5" fill="{ORANGE}"/>'
        f'<text class="leg" x="{x0 + 1050}" y="{legend_y}">{rs["smoke"]} broke the service · {rs["malformed"]} never applied</text>'
        f"</g></g>"
    )
    return {
        "slug": "05-finding-is-solved",
        "kicker": "Vulnerability mode · defender seat",
        "title": f'Finding real bugs isn’t the problem: <em>{n} of {n}</em> found',
        "sub": f"So noise is what separates auditors. The {s} attacks that won all beat the patch, not the review. Each square is one planted bug.",
        "svg": "\n".join(cells) + legend,
        "svg_h": legend_y + 40,
        "note": "",
        "script": f"""
tl.fromTo(".cell", {{opacity:0, scale:.4}}, {{opacity:1, scale:1, duration:.4, ease:"back.out(2)", stagger:{{each:.012, from:"start"}}, transformOrigin:"50% 50%"}}, .8);
tl.fromTo("#legend", {{opacity:0}}, {{opacity:1, duration:.4}}, 2.2);
tl.fromTo("#leg-fn", {{opacity:0}}, {{opacity:1, duration:.4}}, 3.4);
tl.to(".fn.inc", {{fill:"{RED}", duration:.35, stagger:.05}}, 3.0);
tl.to(".fn.smoke, .fn.mal", {{fill:"{ORANGE}", duration:.35, stagger:.05}}, 3.3);
tl.fromTo(".fn", {{scale:1}}, {{scale:1.12, duration:.25, yoyo:true, repeat:1, ease:"power2.out", stagger:.04, transformOrigin:"50% 50%"}}, 3.0);
tl.fromTo("#callout", {{opacity:0, y:10}}, {{opacity:1, y:0, duration:.45, ease:"power3.out"}}, 3.6);
""",
        "callout": f'<div id="callout" class="callout red">{s} / {n}<small>beat the patch</small></div>',
    }


# label offsets for the scatter, by short name: (dx, dy, anchor)
SCATTER_LABELS = {
    "Grok 4.7": (0, -30, "middle"),
    "GLM-5.3 Max": (-22, -10, "end"),
    "Gemini 4 Argon": (0, 42, "middle"),
    "GPT-6 Astra": (0, 42, "middle"),
    "DeepSeek V4 Pro": (-20, 8, "end"),
    "GLM-5.2": (20, 8, "start"),
    "GLM-5.3 Flash": (0, -30, "middle"),
    "GPT-6.1": (0, 40, "middle"),
    "Opus 5.5": (0, 40, "middle"),
    "GLM-5.3": (0, -26, "middle"),
}


def card_price(d):
    ms = [m for m in d["models"] if m["cost"] and m["def_elo"]]
    flash = next(m for m in ms if m["name"] == "GLM-5.3 Flash")
    grok = next(m for m in ms if m["name"] == "Grok 4.7")
    ratio = grok["cost"] / flash["cost"]
    px0, px1, py0, py1 = 170, 1660, 40, 560
    lo, hi = math.log10(0.025), math.log10(1.5)
    e_lo, e_hi = 1200, 1760

    def X(c):
        return px0 + (math.log10(c) - lo) / (hi - lo) * (px1 - px0)

    def Y(e):
        return py1 - (e - e_lo) / (e_hi - e_lo) * (py1 - py0)

    out = []
    for c in (0.03, 0.05, 0.1, 0.25, 0.5, 1.0):
        out.append(f'<line class="grid" x1="{X(c):.1f}" y1="{py0}" x2="{X(c):.1f}" y2="{py1}"/>')
        out.append(f'<text class="tick" x="{X(c):.1f}" y="{py1 + 32}" text-anchor="middle">${c:g}</text>')
    for e in range(1200, 1800, 100):
        out.append(f'<line class="grid" x1="{px0}" y1="{Y(e):.1f}" x2="{px1}" y2="{Y(e):.1f}"/>')
        out.append(f'<text class="tick" x="{px0 - 18}" y="{Y(e) + 6:.1f}" text-anchor="end">{e}</text>')
    out.append(f'<text class="axis" x="{(px0 + px1) / 2}" y="{py1 + 76}" text-anchor="middle">cost per round · log scale</text>')
    out.append(f'<text class="axis" x="{px0 - 120}" y="{(py0 + py1) / 2}" text-anchor="middle" transform="rotate(-90 {px0 - 120} {(py0 + py1) / 2})">audit rating</text>')
    yline = Y(grok["def_elo"]) - 70
    out.append(
        f'<g id="span"><line class="span" x1="{X(flash["cost"]):.1f}" y1="{yline:.1f}" x2="{X(grok["cost"]):.1f}" y2="{yline:.1f}"/>'
        f'<text class="spanl" x="{(X(flash["cost"]) + X(grok["cost"])) / 2:.1f}" y="{yline - 18:.1f}" text-anchor="middle">{ratio:.0f}× the price for +{round(grok["def_elo"] - flash["def_elo"])} rating</text></g>'
    )
    for m in ms:
        hot = m is flash or m is grok
        color = TEAL if m is flash else GOLD2 if m is grok else "#7A8CA3"
        x, y = X(m["cost"]), Y(m["def_elo"])
        r = 15 if hot else 10
        dx, dy, anchor = SCATTER_LABELS.get(m["name"], (18, 6, "start"))
        cls = "plbl hot" if hot else "plbl"
        lbl = m["name"] + (f'  ${m["cost"]:.2f}' if hot else "")
        out.append(
            f'<g class="pt{" hotpt" if hot else ""}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>'
            f'<text class="{cls}" x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" fill="{color}">{esc(lbl)}</text></g>'
        )
    ci = max(flash["def_ci"], grok["def_ci"])
    return {
        "slug": "06-price",
        "kicker": "Defender seat · audit rating vs cost",
        "title": f'Same audit rating. <em>{ratio:.0f}× cheaper.</em>',
        "sub": f'GLM-5.3 Flash: ${flash["cost"]:.2f} a round, false alarms on {pct(flash["fpr"])} of clean code. Grok 4.7: ${grok["cost"]:.2f}, false alarms on {pct(grok["fpr"])}.',
        "svg": "\n".join(out),
        "svg_h": py1 + 100,
        "chart_top": 320,
        "note": f'Ratings carry up to ±{round(ci)} at 95% ({flash["def_n"]}–{grok["def_n"]} audits each): the top of the board is a statistical tie.',
        "script": """
tl.fromTo(".pt", {opacity:0, scale:0}, {opacity:1, scale:1, duration:.45, ease:"back.out(2.2)", stagger:.06, transformOrigin:"50% 50%"}, .9);
tl.to(".pt:not(.hotpt)", {opacity:.7, duration:.4}, 2.6);
tl.fromTo(".hotpt", {scale:1}, {scale:1.15, duration:.3, yoyo:true, repeat:1, ease:"power2.out", transformOrigin:"50% 50%"}, 2.7);
tl.fromTo("#span line", {strokeDasharray:1500, strokeDashoffset:1500}, {strokeDashoffset:0, duration:.8, ease:"power2.inOut"}, 3.0);
tl.fromTo("#span text", {opacity:0, y:8}, {opacity:1, y:0, duration:.4}, 3.5);
""",
        "callout": "",
    }


def card_attackers(d):
    names = {m["agent"]: m["name"] for m in d["models"]}
    ms = [m for m in d["models"] if m["attack_fn"] + m["attack_tp"]]
    ms.sort(key=lambda m: (-m["attack_fn"] / (m["attack_fn"] + m["attack_tp"]), -(m["attack_fn"] + m["attack_tp"])))
    rows = []
    for m in ms:
        n = m["attack_fn"] + m["attack_tp"]
        s = m["attack_fn"] / n
        rows.append((m["name"], "", s, f'{m["attack_fn"]} of {n} beat the patch', RED if m is ms[0] else GREY if s else "rgba(122,140,163,.4)"))
    svg, h = bar_rows(rows, y0=50, row_h=54, bar_h=28)
    top = ms[0]
    opp = {}
    for r in d["ledger"]:
        if r["attacker"] == top["agent"] and r["theta"] == 1 and r["outcome"] == "FN":
            opp[names[r["defender"]]] = opp.get(names[r["defender"]], 0) + 1
    # the board shows whole ratings, so a tie on the board is a tie here
    elos = sorted((round(m["def_elo"] or 0) for m in d["models"]), reverse=True)
    best_def = [m["name"] for m in sorted(d["models"], key=lambda m: -(m["def_elo"] or 0)) if round(m["def_elo"] or 0) >= elos[2]]
    faced = {names[r["defender"]] for r in d["ledger"] if r["attacker"] == top["agent"] and r["theta"] == 1}
    unfaced = [b for b in best_def if b not in faced]
    wins = ", ".join(f"{k} ×{v}" if v > 1 else k for k, v in sorted(opp.items(), key=lambda kv: -kv[1]))
    if unfaced == best_def:
        tail = f" It never drew any of the top auditors ({', '.join(unfaced)})."
    else:
        tail = f" It never drew {', '.join(unfaced)}." if unfaced else ""
    note = f"Its wins: {wins}." + tail
    return {
        "slug": "08-best-attacker",
        "kicker": "Vulnerability mode · exploits that beat the patch",
        "title": f'{esc(top["name"])}’s exploit still worked after the fix <em>{top["attack_fn"]} of {top["attack_fn"] + top["attack_tp"]}</em> times',
        "sub": "Every planted bug came with a working exploit, run against the service. Auditors spotted them; the patch failed. Models that refused every attack are left out.",
        "svg": svg,
        "svg_h": h + 100,
        "note": note,
        "script": BAR_SCRIPT,
        "callout": "",
    }


def _box(x, y, w, h, label, text, color=GOLD, cls="box"):
    return (
        f'<g class="{cls}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="boxr" stroke="{color}"/>'
        f'<text class="boxk" x="{x + 26}" y="{y + 44}" fill="{color}">{esc(label)}</text>'
        f'<text class="boxt" x="{x + 26}" y="{y + 92}">{esc(text)}</text></g>'
    )


def _arrow(x1, y1, x2, y2):
    return f'<path class="arrow" d="M{x1},{y1} C{(x1 + x2) / 2},{y1} {(x1 + x2) / 2},{y2} {x2},{y2}" marker-end="url(#ah)"/>'


def card_how(d):
    n1, s1 = d["vuln_played"], d["survived"]
    tn, fp = d["clean_tn"], d["clean_fp"]
    vy, cy = 30, 360
    out = [f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GOLD}"/></marker></defs>']
    out.append(f'<g class="step s1">{_box(0, 195, 300, 150, "Attacker", "builds a Notes API")}</g>')
    out.append(f'<g class="step s2">{_arrow(300, 270, 370, vy + 75)}{_box(370, vy, 390, 150, "Vulnerability mode", "plants a working exploit", RED)}'
               f'{_arrow(300, 270, 370, cy + 75)}{_box(370, cy, 390, 150, "Control mode", "ships clean code", TEAL)}</g>')
    out.append(f'<g class="step s3">{_arrow(760, vy + 75, 830, vy + 75)}{_box(830, vy, 340, 150, "Defender", "audits and patches")}'
               f'{_arrow(760, cy + 75, 830, cy + 75)}{_box(830, cy, 340, 150, "Defender", "audits the code")}</g>')

    def outcome(y, text, n, winner, color):
        return (f'<g class="oc"><rect x="1240" y="{y}" width="460" height="66" rx="10" class="ocr" stroke="{color}"/>'
                f'<text class="oct" x="1262" y="{y + 43}">{esc(text)}</text>'
                f'<text class="ocn" x="1680" y="{y + 43}" text-anchor="end" fill="{color}">{n} · {winner}</text></g>')

    out.append('<g class="step s4">'
               + _arrow(1170, vy + 75, 1240, vy + 33) + _arrow(1170, vy + 75, 1240, vy + 117)
               + outcome(vy, "finds it, the fix holds", n1 - s1, "defender", TEAL)
               + outcome(vy + 84, "the patch fails", s1, "attacker", RED)
               + _arrow(1170, cy + 75, 1240, cy + 33) + _arrow(1170, cy + 75, 1240, cy + 117)
               + outcome(cy, "calls it clean", tn, "defender", TEAL)
               + outcome(cy + 84, "raises a false alarm", fp, "attacker", RED)
               + "</g>")
    return {
        "slug": "02-how-it-works",
        "kicker": "Methodology · one round",
        "title": "One model builds. The other audits. <em>Two modes.</em>",
        "sub": "Counts are the rounds actually played this season, per outcome.",
        "svg": "\n".join(out),
        "svg_h": cy + 175,
        "chart_top": 310,
        "note": "Rounds where a model refused or a run failed are left out of the counts.",
        "script": """
tl.fromTo(".s1", {opacity:0, x:-20}, {opacity:1, x:0, duration:.45, ease:"power3.out"}, .8);
tl.fromTo(".s2", {opacity:0, x:-20}, {opacity:1, x:0, duration:.45, ease:"power3.out"}, 1.5);
tl.fromTo(".s3", {opacity:0, x:-20}, {opacity:1, x:0, duration:.45, ease:"power3.out"}, 2.2);
tl.fromTo(".s4 .arrow", {opacity:0}, {opacity:1, duration:.3}, 2.9);
tl.fromTo(".oc", {opacity:0, x:-16}, {opacity:1, x:0, duration:.4, ease:"power3.out", stagger:.18}, 3.0);
""",
        "callout": "",
    }


def card_bet(d):
    ms = sorted(d["models"], key=lambda m: -m["net"])
    lo, hi = min(m["net"] for m in ms), max(m["net"] for m in ms)
    lo, hi = math.floor(lo / 5) * 5, math.ceil(hi / 5) * 5
    x0, x1, y0, row_h, bar_h = 330, 1560, 40, 38, 22
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    zero = X(0)
    out = []
    for v in range(lo, hi + 1, 5):
        out.append(f'<line class="grid" x1="{X(v):.1f}" y1="{y0 - 10}" x2="{X(v):.1f}" y2="{y0 + len(ms) * row_h}"/>')
        out.append(f'<text class="tick" x="{X(v):.1f}" y="{y0 + len(ms) * row_h + 34}" text-anchor="middle">{"+" if v > 0 else "−" if v < 0 else ""}${abs(v)}</text>')
    out.append(f'<line class="zero" x1="{zero:.1f}" y1="{y0 - 18}" x2="{zero:.1f}" y2="{y0 + len(ms) * row_h + 4}"/>')
    for i, m in enumerate(ms):
        v = m["net"]
        cy = y0 + i * row_h + row_h / 2
        edge = i in (0, len(ms) - 1)
        color = (TEAL if v >= 0 else RED) if edge else ("#3E8F89" if v >= 0 else "#9A4B4B")
        w = abs(X(v) - zero)
        flip = "" if v >= 0 else " scale(-1,1)"
        lab = f'{"+" if v >= 0 else "−"}${abs(v):.2f}'
        lx, anchor = (X(v) + 12, "start") if v >= 0 else (X(v) - 12, "end")
        out.append(
            f'<g class="row"><text class="name{"" if edge else " dimname"}" x="{x0 - 22}" y="{cy + 2}" text-anchor="end" dominant-baseline="middle">{esc(m["name"])}</text>'
            f'<g transform="translate({zero:.1f},0){flip}"><rect class="nbar" x="0" y="{cy - bar_h / 2}" width="{max(w, 3):.1f}" height="{bar_h}" rx="3" fill="{color}"/></g>'
            f'<text class="val" x="{lx:.1f}" y="{cy + 2}" text-anchor="{anchor}" dominant-baseline="middle" fill="{color if edge else LABEL_GREY}">{lab}</text></g>'
        )
    top, bot = ms[0], ms[-1]
    return {
        "slug": "03-every-token-is-a-bet",
        "kicker": "Financial incentive · net winnings over the season",
        "title": "Every token is a bet. <em>The winner takes the loser’s spend.</em>",
        "sub": "Each model stakes what its own tokens cost. Attacker spends $1, defender spends $10 and misses: attacker +$10, defender −$10.",
        "svg": "\n".join(out),
        "svg_h": y0 + len(ms) * row_h + 60,
        "chart_top": 420,
        "note": f"Best: {top['name']} ({'+' if top['net'] >= 0 else '−'}${abs(top['net']):.2f}). Worst: {bot['name']} (−${abs(bot['net']):.2f}).",
        "script": """
tl.fromTo(".row", {opacity:0}, {opacity:1, duration:.3, stagger:.04}, .8);
tl.fromTo(".nbar", {scaleX:0}, {scaleX:1, duration:.8, ease:"power3.out", stagger:.06, transformOrigin:"left center"}, 1.1);
tl.fromTo(".row .val", {opacity:0}, {opacity:1, duration:.3, stagger:.06}, 1.6);
""",
        "callout": "",
    }


def card_pick(d):
    by = {m["name"]: m for m in d["models"]}
    flash, grok = by["GLM-5.3 Flash"], by["Grok 4.7"]
    full = [m for m in d["models"] if m["att_rounds"] and m["att_refused"] == m["att_rounds"]]
    full_n = sum(m["att_rounds"] for m in full)
    quiet = [m["name"] for m in sorted(d["models"], key=lambda m: m["name"]) if m["fpr"] == 0]
    sure = [m for m in d["models"] if m["tp"] >= 10 and m["fn"] == 0]
    rows = [
        ("One auditor", "Grok 4.7 · Gemini 4 Argon · GLM-5.3 Max", "a statistical tie at the top"),
        ("Audit for pennies", "GLM-5.3 Flash", f"${flash['cost']:.2f} a round vs ${grok['cost']:.2f}"),
        ("Fewest false alarms", " · ".join(quiet), "0% on clean code"),
        ("You suspect a bug", " · ".join(m["name"] for m in sure), " and ".join(f"{m['tp']}–{m['fn']}" for m in sure[:1]) + " on planted bugs"),
        ("Test your own scanner", "DeepSeek V4.1 Flash", "never refused to plant one"),
        ("Red teaming", "not Claude or OpenAI", f"they refused {full_n} of {full_n}"),
    ]
    out = []
    rh = 84
    for i, (need, pick, why) in enumerate(rows):
        y = 20 + i * rh
        hot = i == 2
        out.append(
            f'<g class="prow"><rect x="0" y="{y}" width="1700" height="{rh - 10}" rx="10" class="{"prr hotr" if hot else "prr"}"/>'
            f'<text class="pneed" x="28" y="{y + 48}">{esc(need)}</text>'
            f'<text class="ppick{" hot" if hot else ""}" x="470" y="{y + 48}">{esc(pick)}</text>'
            f'<text class="pwhy" x="1672" y="{y + 48}" text-anchor="end">{esc(why)}</text></g>'
        )
    return {
        "slug": "09-which-model",
        "kicker": "Results · cheat sheet",
        "title": "Which model should audit <em>your</em> code?",
        "sub": "From 288 rounds. The quiet auditors are highlighted: on clean code, the field cried wolf 31% of the time.",
        "svg": "\n".join(out),
        "svg_h": 20 + len(rows) * rh + 10,
        "chart_top": 330,
        "note": "Ratings at the top overlap within their 95% intervals.",
        "script": """
tl.fromTo(".prow", {opacity:0, x:-20}, {opacity:1, x:0, duration:.4, ease:"power3.out", stagger:.22}, .8);
tl.fromTo(".hotr", {opacity:.0}, {opacity:1, duration:.5}, 2.6);
""",
        "callout": "",
    }


def card_read(d):
    stats = [
        (str(d["rounds"]), "rounds played", GOLD2, False),
        (f'{d["planted"]} / {d["planted"]}', "planted bugs found", GOLD2, False),
        (str(d["planted"] - d["survived"]), "fixed for good", GOLD2, False),
        (pct(d["field_fpr"]), "false alarms on clean code", RED, True),
        (str(d["refused"]), "rounds refused", GOLD2, False),
    ]
    out = []
    x = 0
    widths = [300, 330, 300, 420, 300]
    gap = (1700 - sum(widths)) / 4
    for (num, lab, color, hot), w in zip(stats, widths):
        out.append(
            f'<g class="stat"><rect x="{x:.1f}" y="20" width="{w}" height="250" rx="12" class="{"statr hotr" if hot else "statr"}"/>'
            f'<text class="statn{" hot" if hot else ""}" x="{x + 28:.1f}" y="{150}" fill="{color}">{esc(num)}</text>'
            f'<text class="statl" x="{x + 28:.1f}" y="{220}">{esc(lab)}</text></g>'
        )
        x += w + gap
    out.append(f'<g id="cta"><text class="cta" x="0" y="400">Read the full write-up →</text>'
               f'<text class="ctau" x="0" y="470">{SITE}/article</text></g>')
    return {
        "slug": "10-read-more",
        "kicker": "Research · November 2026",
        "title": "Introducing <em>Defuse Arena</em>",
        "sub": "AI models attacking and auditing each other’s code: who finds the bug, who fixes it, who cries wolf.",
        "svg": "\n".join(out),
        "svg_h": 500,
        "chart_top": 330,
        "note": "Compute from Cognition’s Devin ambassador program; the research is independent.",
        "script": """
tl.fromTo(".stat", {opacity:0, y:24}, {opacity:1, y:0, duration:.45, ease:"power3.out", stagger:.15}, .8);
tl.fromTo(".hotr", {opacity:0}, {opacity:1, duration:.5}, 2.0);
tl.fromTo("#cta", {opacity:0, x:-16}, {opacity:1, x:0, duration:.5, ease:"power3.out"}, 2.4);
""",
        "callout": "",
    }


CARDS = (card_hero, card_hero_combo, card_how, card_bet, card_false_alarms, card_patch, card_price, card_refusals, card_attackers, card_pick, card_read)


# --------------------------------------------------------------------------
# project files

INDEX = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1920px; height: 1080px; overflow: hidden; background: #010A13; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1920" data-height="1080">
      <div id="card" data-composition-id="card" data-composition-src="compositions/card.html"
        data-start="0" data-duration="__DUR__" data-track-index="1" data-track-kind="graphics"
        data-width="1920" data-height="1080"></div>
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({ paused: true });
    </script>
  </body>
</html>
"""

CARD = """<template>
  <style>
    @font-face { font-family: "Cinzel"; font-weight: 700; src: url("assets/fonts/cinzel-700.woff2") format("woff2"); }
    @font-face { font-family: "Rajdhani"; font-weight: 500; src: url("assets/fonts/rajdhani-500.woff2") format("woff2"); }
    @font-face { font-family: "Rajdhani"; font-weight: 600; src: url("assets/fonts/rajdhani-600.woff2") format("woff2"); }
    @font-face { font-family: "Rajdhani"; font-weight: 700; src: url("assets/fonts/rajdhani-700.woff2") format("woff2"); }
    #root { position: absolute; inset: 0; overflow: hidden; color: #CDBE91; font-family: "Rajdhani", sans-serif;
      background:
        radial-gradient(1200px 640px at 12% -12%, rgba(10,200,185,.12), transparent 60%),
        radial-gradient(1000px 600px at 95% 0%, rgba(200,170,110,.12), transparent 55%),
        linear-gradient(180deg, #010A13 0%, #06101F 45%, #010A13 100%); }
    #frame { position: absolute; inset: 36px; border: 1px solid rgba(200,170,110,.22); border-radius: 14px; }
    #frame::before { content: ""; position: absolute; inset: 8px; border: 1px solid rgba(200,170,110,.08); border-radius: 9px; }
    #head { position: absolute; left: 110px; right: 110px; top: 96px; }
    #kicker { font-family: "Cinzel", serif; font-weight: 700; font-size: 20px; letter-spacing: .26em; text-transform: uppercase; color: #C8AA6E; }
    #title { margin-top: 18px; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 76px; line-height: 1.02; color: #F0E6D2; letter-spacing: -.005em; max-width: 1560px; }
    #title em { font-style: normal; color: #0AC8B9; white-space: nowrap; }
    #title em.hot { color: #E06060; }
    #head.narrow #title, #head.narrow #sub { max-width: 1240px; }
    #subs { position: relative; }
    #sub2 { position: absolute; left: 0; top: 0; margin-top: 18px; font-size: 30px; font-weight: 600; line-height: 1.3; color: #CDBE91; max-width: 1500px; }
    #sub { margin-top: 18px; font-size: 30px; font-weight: 500; line-height: 1.3; color: #7A8CA3; max-width: 1500px; }
    #chart { position: absolute; left: 110px; right: 110px; top: __CHARTTOP__px; bottom: 140px; }
    #chart svg { display: block; width: 100%; height: 100%; overflow: visible; }
    #foot { position: absolute; left: 110px; right: 110px; bottom: 66px; display: flex; justify-content: space-between; align-items: baseline; gap: 40px; font-size: 24px; color: #8E9DB0; }
    #foot b { font-family: "Cinzel", serif; font-weight: 700; color: #C8AA6E; letter-spacing: .12em; font-size: 22px; white-space: nowrap; }
    #note { max-width: 1250px; }
    .callout { position: absolute; right: 120px; top: 92px; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 120px; line-height: .9; text-align: right; }
    .callout small { display: block; font-size: 26px; letter-spacing: .2em; text-transform: uppercase; font-family: "Cinzel", serif; margin-top: 10px; }
    .callout.red { color: #E06060; }
    .grid { stroke: rgba(200,170,110,.09); stroke-width: 1.5; }
    .tick { fill: #8E9DB0; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 26px; }
    .axis { fill: #7A8CA3; font-family: "Cinzel", serif; font-weight: 700; font-size: 18px; letter-spacing: .18em; text-transform: uppercase; }
    .name { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 31px; }
    .sub { fill: #7A8CA3; font-size: 22px; }
    .val { font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 30px; }
    .track { fill: rgba(200,170,110,.05); }
    .ref { stroke: #C8AA6E; stroke-width: 2; stroke-dasharray: 8 7; }
    .refl { fill: #C8AA6E; font-family: "Cinzel", serif; font-weight: 700; font-size: 24px; letter-spacing: .12em; text-transform: uppercase; }
    .cell { fill: #0AC8B9; }
    .boxr { fill: rgba(15,27,45,.85); stroke-width: 2; }
    .boxk { font-family: "Cinzel", serif; font-weight: 700; font-size: 20px; letter-spacing: .16em; text-transform: uppercase; }
    .boxt { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 32px; }
    .arrow { fill: none; stroke: rgba(200,170,110,.6); stroke-width: 2.5; }
    .ocr { fill: rgba(1,10,19,.7); stroke-width: 2; }
    .oct { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 29px; }
    .ocn { font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 29px; }
    .zero { stroke: #C8AA6E; stroke-width: 2; }
    .dimname { fill: #A3B1C2; }
    .prr { fill: rgba(15,27,45,.7); stroke: rgba(200,170,110,.14); }
    .prr.hotr, .statr.hotr { fill: rgba(224,96,96,.10); stroke: #E06060; stroke-width: 2; }
    .pneed { fill: #C8AA6E; font-family: "Cinzel", serif; font-weight: 700; font-size: 24px; letter-spacing: .08em; text-transform: uppercase; }
    .ppick { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 36px; }
    .ppick.hot { fill: #0AC8B9; }
    .pwhy { fill: #A3B1C2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 30px; }
    .statr { fill: rgba(15,27,45,.75); stroke: rgba(200,170,110,.18); }
    .statn { font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 96px; font-variant-numeric: tabular-nums; }
    .statn.hot { font-size: 110px; }
    .statl { fill: #A3B1C2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 30px; }
    .cta { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 56px; }
    .ctau { fill: #0AC8B9; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 48px; }
    .bigs { fill: #A3B1C2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 30px; }
    .bignum { fill: #E06060; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 300px; font-variant-numeric: tabular-nums; }
    .bigl { fill: #F0E6D2; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 40px; }
    .leg { fill: #CDBE91; font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 28px; }
    .plbl { font-family: "Rajdhani", sans-serif; font-weight: 600; font-size: 27px; paint-order: stroke; stroke: #010A13; stroke-width: 6px; stroke-linejoin: round; }
    .plbl.hot { font-size: 30px; font-weight: 700; }
    .span { stroke: #0AC8B9; stroke-width: 3; stroke-dasharray: 10 8; }
    .spanl { fill: #0AC8B9; font-family: "Rajdhani", sans-serif; font-weight: 700; font-size: 30px; }
  </style>
  <div id="root" data-composition-id="card" data-width="1920" data-height="1080">
    <div id="frame" class="clip" data-start="0" data-duration="__DUR__"></div>
    <div id="head" class="clip __HEADCLS__" data-start="0" data-duration="__DUR__">
      <div id="kicker">__KICKER__</div>
      <h1 id="title">__TITLE__</h1>
      <div id="subs"><p id="sub">__SUB__</p>__SUB2__</div>
    </div>
    __CALLOUT__
    <div id="chart" class="clip" data-start="0" data-duration="__DUR__">
      <svg viewBox="0 0 1700 __SVGH__" preserveAspectRatio="xMinYMid meet" xmlns="http://www.w3.org/2000/svg">__SVG__</svg>
    </div>
    <div id="foot" class="clip" data-start="0" data-duration="__DUR__">
      <span id="note">__NOTE__ Source: __ROUNDS__ rounds, Defuse Arena season 2026.</span>
      <b>__SITE__</b>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({ paused: true });
    tl.fromTo("#kicker", {opacity:0, y:12}, {opacity:1, y:0, duration:.4, ease:"power3.out"}, .05);
    tl.fromTo("#title", {opacity:0, y:22, filter:"blur(8px)"}, {opacity:1, y:0, filter:"blur(0px)", duration:.55, ease:"power4.out"}, .15);
    tl.fromTo("#sub", {opacity:0, y:12}, {opacity:1, y:0, duration:.45, ease:"power3.out"}, .45);
    tl.fromTo("#foot", {opacity:0}, {opacity:1, duration:.5}, .9);
    __SCRIPT__
    window.__timelines["card"] = tl;
  </script>
</template>
"""


def write_project(card: dict, rounds: int, out: Path) -> Path:
    p = out / card["slug"]
    (p / "compositions").mkdir(parents=True, exist_ok=True)
    fonts = p / "assets" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for f in FONTS.glob("*.woff2"):
        shutil.copy2(f, fonts / f.name)
    dur = f'{card.get("dur", DUR):g}'
    (p / "index.html").write_text(INDEX.replace("__DUR__", dur))
    callout = card["callout"]
    if callout:
        callout = callout.replace('class="callout', f'data-start="0" data-duration="{dur}" class="clip callout', 1)
    body = (
        CARD.replace("__DUR__", dur)
        .replace("__KICKER__", esc(card["kicker"]))
        .replace("__TITLE__", card["title"])
        .replace("__SUB__", esc(card["sub"]))
        .replace("__SUB2__", f'<p id="sub2">{esc(card["sub2"])}</p>' if card.get("sub2") else "")
        .replace("__CALLOUT__", callout)
        .replace("__HEADCLS__", "narrow" if card["callout"] else "")
        .replace("__CHARTTOP__", str(card.get("chart_top", 400)))
        .replace("__SVGH__", f'{card["svg_h"]:.0f}')
        .replace("__SVG__", card["svg"])
        .replace("__NOTE__", esc(card["note"]))
        .replace("__ROUNDS__", str(rounds))
        .replace("__SITE__", SITE)
        .replace("__SCRIPT__", card["script"])
    )
    (p / "compositions" / "card.html").write_text(body)
    hf = {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "authoringSkill": "hyperframes",
    }
    (p / "hyperframes.json").write_text(json.dumps(hf, indent=2) + "\n")
    return p


def main() -> None:
    season = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEASON
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    d = season_data(season)
    for make in CARDS:
        print(write_project(make(d), d["rounds"], out))


if __name__ == "__main__":
    main()
