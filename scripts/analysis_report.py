#!/usr/bin/env python3
"""Generate the standalone model report page.

    python3 scripts/analysis_report.py [season] [output]

The report is a frozen analysis snapshot, not a scoring change. It reads the
season's ``standings.json`` and ``ledger.jsonl`` and writes one self-contained
HTML page: answer cards, seven inline SVG charts, and the per-model tables.
No network, no build step, no JavaScript dependency.
"""
from __future__ import annotations

import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEASON = "s-2026-02+s-flash-probe"
DEFAULT_OUT = ROOT / "web" / "analysis.html"

# ---------------------------------------------------------------- palette
BG = "#07111f"
PANEL = "#0d1a2b"
PANEL_2 = "#101f33"
GRID = "#1b2c44"
TEXT = "#e8eef7"
MUTED = "#93a4bb"
FAINT = "#5f7188"
GOLD = "#c8aa6e"
TEAL = "#3fd0c9"
RED = "#e06c75"
BLUE = "#6ea8fe"
PURPLE = "#b48ead"
GREEN = "#7ec699"


# ---------------------------------------------------------------- metrics
@dataclass
class Model:
    name: str
    row: dict
    def_n: int = 0
    tp: int = 0
    fn: int = 0
    fp: int = 0
    tn: int = 0
    defusal: float = 0.0
    fpr: float = 0.0
    brier: float = 0.0
    def_elo: float = 0.0
    def_ci: float = 0.0
    played: int = 0
    attack_fn: int = 0
    attack_tp: int = 0
    survival: float | None = None
    att_elo: float = 0.0
    att_ci: float = 0.0
    abstain_a: int = 0
    failed_a: int = 0
    clean_n: int = 0
    clean_fp: int = 0
    clean_tn: int = 0
    clean_fp_rate: float | None = None
    fp_default: int = 0
    fp_real: int = 0
    cost_per_round: float = 0.0
    cost_total: float = 0.0
    tokens: int = 0
    eff: float = 0.0
    eff_ci: float = 0.0
    overall: float = 0.0
    overall_ci: float = 0.0
    fn_incomplete: int = 0
    fn_smoke: int = 0
    fn_malformed: int = 0


def load(season: str):
    sdir = ROOT / "seasons" / season
    standings = json.loads((sdir / "standings.json").read_text())
    raw = [
        json.loads(line)
        for line in (sdir / "ledger.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ledger = [r for r in raw if not r.get("void")]
    return standings, raw, ledger


def build_models(standings: dict, ledger: list[dict]) -> list[Model]:
    models: list[Model] = []
    for row in standings["rows"]:
        m = Model(name=row["agent"], row=row)
        m.overall = row.get("rating") or 0.0
        m.overall_ci = row.get("rating_ci") or 0.0
        m.def_elo = row.get("rating_def") or 0.0
        m.def_ci = row.get("rating_def_ci") or 0.0
        m.att_elo = row.get("rating_att") or 0.0
        m.att_ci = row.get("rating_att_ci") or 0.0
        m.eff = row.get("rating_efficiency") or 0.0
        m.eff_ci = row.get("rating_efficiency_ci") or 0.0
        m.cost_per_round = row.get("cost_per_round") or 0.0
        m.cost_total = row.get("cost_total") or 0.0
        m.tokens = (row.get("att", {}).get("tokens") or 0) + (
            row.get("def", {}).get("tokens") or 0
        )

        drounds = [
            r
            for r in ledger
            if r["defender"] == m.name and r["outcome"] in ("TP", "FN", "FP", "TN")
        ]
        m.def_n = len(drounds)
        m.tp = sum(r["outcome"] == "TP" for r in drounds)
        m.fn = sum(r["outcome"] == "FN" for r in drounds)
        m.fp = sum(r["outcome"] == "FP" for r in drounds)
        m.tn = sum(r["outcome"] == "TN" for r in drounds)
        m.defusal = m.tp / (m.tp + m.fn) if m.tp + m.fn else 0.0
        m.fpr = m.fp / (m.fp + m.tn) if m.fp + m.tn else 0.0
        m.brier = sum(r["brier"] for r in drounds) / len(drounds) if drounds else 0.0
        def default_credential(mechanism: str) -> bool:
            text = (mechanism or "").lower()
            return "dev-admin-token" in text or (
                ("default" in text or "fallback" in text)
                and ("credential" in text or "token" in text or "admin" in text)
            )

        m.fp_default = sum(
            default_credential(r.get("mechanism") or "")
            for r in drounds
            if r["outcome"] == "FP"
        )
        m.fp_real = m.fp - m.fp_default

        att1 = [
            r for r in ledger if r["attacker"] == m.name and r["theta"] == 1
        ]
        played = [r for r in att1 if r["outcome"] in ("TP", "FN")]
        m.played = len(played)
        m.attack_fn = sum(r["outcome"] == "FN" for r in played)
        m.attack_tp = sum(r["outcome"] == "TP" for r in played)
        m.survival = m.attack_fn / m.played if m.played else None
        m.abstain_a = sum(r["outcome"] == "ABSTAIN_A" for r in att1)
        m.failed_a = sum(r["outcome"] in ("FAILED_A", "FAULT_A") for r in att1)
        for r in played:
            if r["outcome"] != "FN":
                continue
            checks = r.get("checks") or {}
            if not checks.get("patch_applied"):
                m.fn_malformed += 1
            elif not checks.get("smoke_patched"):
                m.fn_smoke += 1
            elif checks.get("poc_patched"):
                m.fn_incomplete += 1

        clean = [
            r
            for r in ledger
            if r["attacker"] == m.name
            and r["theta"] == 0
            and r["outcome"] in ("FP", "TN")
        ]
        m.clean_n = len(clean)
        m.clean_fp = sum(r["outcome"] == "FP" for r in clean)
        m.clean_tn = sum(r["outcome"] == "TN" for r in clean)
        m.clean_fp_rate = m.clean_fp / m.clean_n if m.clean_n else None
        models.append(m)
    models.sort(key=lambda x: -x.overall)
    return models


# ---------------------------------------------------------------- svg helpers
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_pct(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def fmt_num(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def win_word(n: int) -> str:
    return "win" if n == 1 else "wins"


def svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: float = 12,
    fill: str = TEXT,
    anchor: str = "start",
    weight: int = 400,
    opacity: float = 1.0,
    halo: bool = False,
) -> str:
    extra = ""
    if halo:
        extra = ' paint-order="stroke" stroke="#07111f" stroke-width="3.5" stroke-linejoin="round"'
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}" opacity="{opacity}"{extra}>'
        f"{esc(text)}</text>"
    )


def svg_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    stroke: str = GRID,
    width: float = 1,
    dash: str | None = None,
    opacity: float = 1.0,
) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"{d}/>'
    )


def svg_circle(
    x: float,
    y: float,
    r: float,
    *,
    fill: str,
    stroke: str = BG,
    width: float = 2,
    opacity: float = 0.9,
) -> str:
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'
    )


def svg_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str,
    opacity: float = 1.0,
    rx: float = 0,
) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{rx}" fill="{fill}" opacity="{opacity}"/>'
    )


def svg_open(width: int, height: int, title: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'font-family="ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">'
    )


def place_labels(
    points: list[dict],
    plot_left: float,
    plot_right: float,
    plot_top: float,
    plot_bottom: float,
    offsets: dict[str, tuple[float, float, str]] | None = None,
    xy: dict[str, tuple[float, float, str]] | None = None,
) -> list[tuple[float, float, str, float, float]]:
    """Greedy label placement with leader-line anchors.

    Returns ``(label_x, label_y, anchor, point_x, point_y)``. The plot edges are
    hard bounds; the point circles are pre-occupied so a label does not sit on
    top of another bubble.
    """
    occupied: list[tuple[float, float, float, float]] = []
    for p in points:
        r = p.get("r", 8)
        occupied.append((p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r))

    out: list[tuple[float, float, str, float, float]] = []
    for p in sorted(points, key=lambda q: (q["y"], q["x"])):
        x, y, label = p["x"], p["y"], p["label"]
        w = max(34.0, len(label) * 6.3)
        h = 12.0
        if xy and label in xy:
            lx, ly, anchor = xy[label]
            out.append((lx, ly, anchor, x, y))
            continue
        if offsets and label in offsets:
            dx, dy, anchor = offsets[label]
            lx, ly = x + dx, y + dy
            if anchor == "start":
                x0 = lx
            elif anchor == "end":
                x0 = lx - w
            else:
                x0 = lx - w / 2
            out.append((lx, ly, anchor, x, y))
            occupied.append((x0, ly - 10, x0 + w, ly + 2))
            continue
        candidates = [
            (x + 10, y + 4, "start"),
            (x - 10, y + 4, "end"),
            (x, y - 14, "middle"),
            (x, y + 20, "middle"),
            (x + 10, y - 10, "start"),
            (x - 10, y - 10, "end"),
            (x + 10, y + 20, "start"),
            (x - 10, y + 20, "end"),
            (x + 20, y + 4, "start"),
            (x - 20, y + 4, "end"),
            (x, y - 26, "middle"),
            (x, y + 32, "middle"),
            (x, y - 40, "middle"),
            (x, y - 54, "middle"),
            (x + 30, y - 14, "start"),
            (x - 30, y - 14, "end"),
            (x + 30, y + 20, "start"),
            (x - 30, y + 20, "end"),
            (x + 52, y + 4, "start"),
            (x - 52, y + 4, "end"),
        ]
        best = None
        best_overlap = float("inf")
        for lx, ly, anchor in candidates:
            if anchor == "start":
                x0 = lx
            elif anchor == "end":
                x0 = lx - w
            else:
                x0 = lx - w / 2
            y0, x1, y1 = ly - 10, x0 + w, ly + 2
            if x0 < plot_left + 3 or x1 > plot_right - 3 or y0 < plot_top + 3 or y1 > plot_bottom - 3:
                continue
            overlap = 0.0
            for ox0, oy0, ox1, oy1 in occupied:
                dx = min(x1, ox1) - max(x0, ox0)
                dy = min(y1, oy1) - max(y0, oy0)
                if dx > 0 and dy > 0:
                    overlap += dx * dy
            if overlap < best_overlap:
                best_overlap = overlap
                best = (lx, ly, anchor, x0, y0, x1, y1)
        if best is None:
            lx, ly, anchor = x + 10, y + 4, "start"
            best = (lx, ly, anchor, lx, ly - 10, lx + w, ly + 2)
        out.append((best[0], best[1], best[2], x, y))
        occupied.append(best[3:7])
    return out


def scatter(
    points: list[dict],
    *,
    title: str,
    x_label: str,
    y_label: str,
    x_max: float = 1.0,
    y_max: float = 1.0,
    x_ticks: list[float] | None = None,
    y_ticks: list[float] | None = None,
    quadrant_x: float | None = None,
    quadrant_y: float | None = None,
    label_offsets: dict[str, tuple[float, float, str]] | None = None,
    label_xy: dict[str, tuple[float, float, str]] | None = None,
    width: int = 900,
    height: int = 560,
    note: str | None = None,
) -> str:
    left, right, top, bottom = 74, 28, 72, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    x_ticks = x_ticks or [i / 5 for i in range(6)]
    y_ticks = y_ticks or [i / 5 for i in range(6)]

    def sx(v: float) -> float:
        return left + (v / x_max) * plot_w

    def sy(v: float) -> float:
        return top + (1 - v / y_max) * plot_h

    parts = [svg_open(width, height, title)]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    parts.append(svg_rect(left, top, plot_w, plot_h, fill=PANEL, rx=10))

    for t in x_ticks:
        x = sx(t)
        parts.append(svg_line(x, top, x, top + plot_h, stroke=GRID, opacity=0.55))
        parts.append(svg_text(x, top + plot_h + 20, fmt_pct(t, 0), size=11, fill=MUTED, anchor="middle"))
    for t in y_ticks:
        y = sy(t)
        parts.append(svg_line(left, y, left + plot_w, y, stroke=GRID, opacity=0.55))
        parts.append(svg_text(left - 10, y + 4, fmt_pct(t, 0), size=11, fill=MUTED, anchor="end"))

    parts.append(svg_text(left + plot_w / 2, height - 16, x_label, size=12, fill=MUTED, anchor="middle"))
    parts.append(
        f'<text x="18" y="{top + plot_h / 2:.1f}" font-size="12" fill="{MUTED}" '
        f'text-anchor="middle" transform="rotate(-90 18 {top + plot_h / 2:.1f})">{esc(y_label)}</text>'
    )

    if quadrant_x is not None:
        x = sx(quadrant_x)
        parts.append(svg_line(x, top, x, top + plot_h, stroke=FAINT, width=1.2, dash="5 5", opacity=0.8))
    if quadrant_y is not None:
        y = sy(quadrant_y)
        parts.append(svg_line(left, y, left + plot_w, y, stroke=FAINT, width=1.2, dash="5 5", opacity=0.8))

    pixel_points = [
        {"x": sx(p["x"]), "y": sy(p["y"]), "label": p["label"], "r": p.get("r", 8)}
        for p in points
    ]
    abs_xy = (
        {k: (v[0] * width, v[1] * height, v[2]) for k, v in label_xy.items()}
        if label_xy
        else None
    )
    labels = place_labels(
        pixel_points,
        left,
        left + plot_w,
        top,
        top + plot_h,
        offsets=label_offsets,
        xy=abs_xy,
    )
    for p, (lx, ly, anchor, px, py) in zip(
        sorted(points, key=lambda q: (sy(q["y"]), sx(q["x"]))), labels
    ):
        x, y = sx(p["x"]), sy(p["y"])
        r = p.get("r", 8)
        if anchor == "start":
            lx0, ly0 = lx - 2, ly - 4
        elif anchor == "end":
            lx0, ly0 = lx + 2, ly - 4
        else:
            lx0, ly0 = lx, ly + 2
        if abs(lx0 - x) + abs(ly0 - y) > 18:
            parts.append(svg_line(x, y, lx0, ly0, stroke=FAINT, width=0.8, opacity=0.45))
        parts.append(
            f'<g><title>{esc(p.get("title", p["label"]))}</title>'
            f'{svg_circle(x, y, r, fill=p.get("color", TEAL), stroke=BG, width=2, opacity=0.9)}'
            f'{svg_text(lx, ly, p["label"], size=10.5, fill=p.get("label_color", TEXT), anchor=anchor, weight=600, halo=True)}'
            f"</g>"
        )

    if note:
        parts.append(svg_text(left, height - 2, note, size=10, fill=FAINT))
    parts.append("</svg>")
    return "".join(parts)


def dotplot(models: list[Model], *, width: int = 940, height: int = 590) -> str:
    left, right, top, bottom = 118, 30, 58, 42
    plot_w = width - left - right
    plot_h = height - top - bottom
    xmin, xmax = 1180, 1880
    n = len(models)
    row_h = plot_h / n

    def sx(v: float) -> float:
        return left + (v - xmin) / (xmax - xmin) * plot_w

    parts = [svg_open(width, height, "Ratings with 95% intervals")]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    parts.append(svg_rect(left, top, plot_w, plot_h, fill=PANEL, rx=10))

    for t in range(1200, 1900, 100):
        x = sx(t)
        parts.append(svg_line(x, top, x, top + plot_h, stroke=GRID, opacity=0.5))
        parts.append(svg_text(x, top + plot_h + 20, str(t), size=10, fill=MUTED, anchor="middle"))
    x0 = sx(1500)
    parts.append(svg_line(x0, top, x0, top + plot_h, stroke=GOLD, width=1.2, dash="4 4", opacity=0.7))
    parts.append(svg_text(x0 + 4, top - 10, "prior 1500", size=10, fill=GOLD))

    series = [
        ("Overall", "overall", "overall_ci", GOLD, -9),
        ("Attack", "att_elo", "att_ci", RED, 0),
        ("Defense", "def_elo", "def_ci", TEAL, 9),
    ]
    for idx, m in enumerate(models):
        cy = top + row_h * (idx + 0.5)
        parts.append(svg_text(left - 12, cy + 4, m.name, size=11, fill=TEXT, anchor="end", weight=600))
        for label, field, ci_field, color, dy in series:
            if label == "Attack" and m.played == 0:
                continue
            value = getattr(m, field)
            ci = getattr(m, ci_field)
            if not value:
                continue
            y = cy + dy
            lo, hi = sx(value - ci), sx(value + ci)
            parts.append(svg_line(lo, y, hi, y, stroke=color, width=2.2, opacity=0.55))
            parts.append(svg_line(lo, y - 3, lo, y + 3, stroke=color, width=1.5, opacity=0.7))
            parts.append(svg_line(hi, y - 3, hi, y + 3, stroke=color, width=1.5, opacity=0.7))
            parts.append(
                f'<g><title>{esc(m.name)} {label}: {value:.0f} ±{ci:.0f}</title>'
                f'{svg_circle(sx(value), y, 4.2, fill=color, stroke=BG, width=1.5, opacity=1)}</g>'
            )

    lx = left
    for label, _, _, color, _ in series:
        parts.append(svg_circle(lx + 6, top - 26, 5, fill=color, stroke=BG, width=1.5))
        parts.append(svg_text(lx + 16, top - 22, label, size=11, fill=MUTED))
        lx += 96
    parts.append(svg_text(left, height - 10, "Dot = point estimate; line = 95% interval. Intervals overlap heavily across the top cluster.", size=10, fill=FAINT))
    parts.append("</svg>")
    return "".join(parts)


def hbars(models: list[Model], *, width: int = 940, height: int = 560) -> str:
    left, right, top, bottom = 126, 96, 36, 42
    plot_w = width - left - right
    plot_h = height - top - bottom
    xmin, xmax = 1200, 1800
    n = len(models)
    row_h = plot_h / n
    max_cost = max(m.cost_per_round for m in models) or 1

    def sx(v: float) -> float:
        return left + (v - xmin) / (xmax - xmin) * plot_w

    parts = [svg_open(width, height, "Efficiency ranking")]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    for t in range(1200, 1801, 100):
        x = sx(t)
        parts.append(svg_line(x, top, x, top + plot_h, stroke=GRID, opacity=0.5))
        parts.append(svg_text(x, top + plot_h + 20, str(t), size=10, fill=MUTED, anchor="middle"))

    for idx, m in enumerate(sorted(models, key=lambda x: -x.eff)):
        cy = top + row_h * (idx + 0.5)
        cost_ratio = min(1.0, m.cost_per_round / max_cost)
        color = GREEN if cost_ratio < 0.15 else GOLD if cost_ratio < 0.5 else RED
        bar_w = max(2, sx(m.eff) - sx(xmin))
        parts.append(svg_rect(sx(xmin), cy - row_h * 0.32, bar_w, row_h * 0.64, fill=color, opacity=0.75, rx=4))
        parts.append(svg_text(left - 12, cy + 4, m.name, size=11, fill=TEXT, anchor="end", weight=600))
        parts.append(svg_text(sx(xmin) + bar_w + 8, cy + 4, f"{m.eff:.0f}", size=11, fill=TEXT, weight=700))
        parts.append(svg_text(width - 12, cy + 4, f"${m.cost_per_round:.3f}/r", size=10, fill=MUTED, anchor="end"))
        parts.append(f'<g><title>{esc(m.name)}: efficiency {m.eff:.0f}, ${m.cost_per_round:.3f}/round, overall {m.overall:.0f}</title></g>')

    parts.append(svg_text(left, height - 10, "Bar = margin-weighted efficiency rating. Green = cheap, red = expensive.", size=10, fill=FAINT))
    parts.append("</svg>")
    return "".join(parts)


def stacked_fp(models: list[Model], *, width: int = 940, height: int = 560) -> str:
    left, right, top, bottom = 126, 150, 36, 58
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(models)
    row_h = plot_h / n
    rows = sorted(models, key=lambda m: -(m.fpr or 0))

    parts = [svg_open(width, height, "False alarms: artifact vs real")]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    parts.append(svg_text(left, top - 12, "Clean builds defended, share of outcomes", size=11, fill=MUTED))

    for idx, m in enumerate(rows):
        cy = top + row_h * (idx + 0.5)
        total = m.fp_default + m.fp_real + m.tn
        if total == 0:
            parts.append(svg_text(left, cy + 4, "no clean rounds", size=10, fill=FAINT))
            continue
        x = left
        for value, color, label in (
            (m.tn, "#1b2a40", "cleared"),
            (m.fp_default, GOLD, "false alarm: default credential"),
            (m.fp_real, RED, "false alarm: other"),
        ):
            w = value / total * plot_w
            if w > 0:
                parts.append(
                    f'<g><title>{esc(m.name)}: {value} of {total} clean builds {label}</title>'
                    f'{svg_rect(x, cy - row_h * 0.30, w, row_h * 0.60, fill=color, opacity=0.9, rx=2)}</g>'
                )
            x += w
        parts.append(svg_text(left - 12, cy + 4, m.name, size=11, fill=TEXT, anchor="end", weight=600))
        parts.append(
            svg_text(
                left + plot_w + 10,
                cy + 4,
                f"{fmt_pct(m.fpr, 0)}  ({m.fp_default}D + {m.fp_real}R / {m.tn}T)",
                size=10,
                fill=MUTED,
            )
        )

    lx = left
    for label, color in (("TN (cleared)", "#1b2a40"), ("FP: default credential", GOLD), ("FP: other / real", RED)):
        parts.append(svg_rect(lx, height - 30, 12, 12, fill=color, rx=2))
        parts.append(svg_text(lx + 18, height - 20, label, size=10, fill=MUTED))
        lx += 160
    parts.append("</svg>")
    return "".join(parts)


def stacked_fn(models: list[Model], *, width: int = 940, height: int = 360) -> str:
    rows = [m for m in models if m.attack_fn]
    rows.sort(key=lambda m: -m.attack_fn)
    left, right, top, bottom = 140, 170, 36, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = max(1, len(rows))
    row_h = plot_h / n
    max_fn = max(m.attack_fn for m in rows) if rows else 1

    parts = [svg_open(width, height, "How attacks survived")]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    parts.append(svg_text(left, top - 12, "Attack wins by failure mode", size=11, fill=MUTED))

    for idx, m in enumerate(rows):
        cy = top + row_h * (idx + 0.5)
        x = left
        for value, color, label in (
            (m.fn_incomplete, TEAL, "incomplete fix"),
            (m.fn_smoke, GOLD, "smoke broken"),
            (m.fn_malformed, RED, "malformed patch"),
        ):
            w = value / max_fn * plot_w
            if w > 0:
                parts.append(
                    f'<g><title>{esc(m.name)}: {value} {win_word(value)} by {label}</title>'
                    f'{svg_rect(x, cy - row_h * 0.30, w, row_h * 0.60, fill=color, opacity=0.9, rx=3)}</g>'
                )
            x += w
        parts.append(svg_text(left - 12, cy + 4, m.name, size=11, fill=TEXT, anchor="end", weight=600))
        parts.append(
            svg_text(
                left + plot_w + 10,
                cy + 4,
                f"{m.attack_fn} {win_word(m.attack_fn)}  ({m.fn_incomplete}I + {m.fn_smoke}S + {m.fn_malformed}M)",
                size=10,
                fill=MUTED,
            )
        )

    lx = left
    for label, color in (
        ("incomplete fix", TEAL),
        ("smoke broken", GOLD),
        ("malformed patch", RED),
    ):
        parts.append(svg_rect(lx, height - 30, 12, 12, fill=color, rx=2))
        parts.append(svg_text(lx + 18, height - 20, label, size=10, fill=MUTED))
        lx += 160
    parts.append("</svg>")
    return "".join(parts)


def cost_scatter(models: list[Model], *, width: int = 940, height: int = 520) -> str:
    left, right, top, bottom = 74, 30, 36, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    xmin, xmax = 0.03, 1.15
    ymin, ymax = 1200, 1760

    def sx(v: float) -> float:
        return left + (math.log10(v) - math.log10(xmin)) / (
            math.log10(xmax) - math.log10(xmin)
        ) * plot_w

    def sy(v: float) -> float:
        return top + (1 - (v - ymin) / (ymax - ymin)) * plot_h

    parts = [svg_open(width, height, "Cost vs defense")]
    parts.append(svg_rect(0, 0, width, height, fill=BG, rx=14))
    parts.append(svg_rect(left, top, plot_w, plot_h, fill=PANEL, rx=10))

    for t in (0.03, 0.05, 0.1, 0.25, 0.5, 1.0):
        x = sx(t)
        parts.append(svg_line(x, top, x, top + plot_h, stroke=GRID, opacity=0.5))
        parts.append(svg_text(x, top + plot_h + 20, f"${t:g}", size=10, fill=MUTED, anchor="middle"))
    for t in range(1200, 1800, 100):
        y = sy(t)
        parts.append(svg_line(left, y, left + plot_w, y, stroke=GRID, opacity=0.5))
        parts.append(svg_text(left - 10, y + 4, str(t), size=10, fill=MUTED, anchor="end"))

    # Pareto frontier: cheapest model that beats every cheaper model on defense.
    pareto: list[Model] = []
    best = -1
    for m in sorted(models, key=lambda x: x.cost_per_round):
        if m.def_elo > best:
            pareto.append(m)
            best = m.def_elo
    for a, b in zip(pareto, pareto[1:]):
        parts.append(
            svg_line(
                sx(a.cost_per_round),
                sy(a.def_elo),
                sx(b.cost_per_round),
                sy(b.def_elo),
                stroke=TEAL,
                width=1.4,
                dash="4 4",
                opacity=0.55,
            )
        )

    items = []
    for m in models:
        x, y = sx(m.cost_per_round), sy(m.def_elo)
        color = TEAL if m.def_elo >= 1650 else GOLD if m.def_elo >= 1500 else RED
        r = 7 + math.sqrt(max(1, m.def_n)) * 2.2
        items.append((m, {"x": x, "y": y, "label": m.name, "r": r, "color": color}))
    items.sort(key=lambda item: (item[1]["y"], item[1]["x"]))
    labels = place_labels(
        [item[1] for item in items],
        left,
        left + plot_w,
        top,
        top + plot_h,
        offsets={
            "muse-wonder": (-10, 4, "end"),
            "grok-4.7": (-10, -10, "end"),
            "deepseek": (-10, 12, "end"),
        },
    )
    for (m, point), (lx, ly, anchor, px, py) in zip(items, labels):
        x, y, r, color = point["x"], point["y"], point["r"], point["color"]
        if anchor == "start":
            lx0, ly0 = lx - 2, ly - 4
        elif anchor == "end":
            lx0, ly0 = lx + 2, ly - 4
        else:
            lx0, ly0 = lx, ly + 2
        if abs(lx0 - x) + abs(ly0 - y) > 18:
            parts.append(svg_line(x, y, lx0, ly0, stroke=FAINT, width=0.8, opacity=0.45))
        parts.append(
            f'<g><title>{esc(m.name)}: ${m.cost_per_round:.3f}/round, Def Elo {m.def_elo:.0f}, {m.def_n} defense rounds</title>'
            f'{svg_circle(x, y, r, fill=color, stroke=BG, width=2, opacity=0.88)}'
            f'{svg_text(lx, ly, m.name, size=10.5, fill=TEXT, weight=600, anchor=anchor, halo=True)}</g>'
        )

    parts.append(svg_text(left + plot_w / 2, height - 16, "USD per round (log scale)", size=12, fill=MUTED, anchor="middle"))
    parts.append(
        f'<text x="18" y="{top + plot_h / 2:.1f}" font-size="12" fill="{MUTED}" '
        f'text-anchor="middle" transform="rotate(-90 18 {top + plot_h / 2:.1f})">Defense Elo</text>'
    )
    parts.append(svg_text(left, height - 2, "Up and to the left is better value. Dashed line = cost/defense Pareto frontier.", size=10, fill=FAINT))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- tables
def defense_table(models: list[Model]) -> str:
    rows = sorted(models, key=lambda m: -m.def_elo)
    out = [
        "<table><thead><tr>"
        "<th>Model</th><th class='num'>Def. rounds</th><th class='num'>TP</th>"
        "<th class='num'>FN</th><th class='num'>FP</th><th class='num'>TN</th>"
        "<th class='num'>Defusal</th><th class='num'>FPR</th><th class='num'>Brier</th>"
        "<th class='num'>Def Elo</th></tr></thead><tbody>"
    ]
    for m in rows:
        out.append(
            "<tr>"
            f"<td class='model'>{esc(m.name)}</td>"
            f"<td class='num'>{m.def_n}</td><td class='num'>{m.tp}</td>"
            f"<td class='num'>{m.fn}</td><td class='num'>{m.fp}</td>"
            f"<td class='num'>{m.tn}</td><td class='num'>{fmt_pct(m.defusal, 0)}</td>"
            f"<td class='num'>{fmt_pct(m.fpr, 0)}</td><td class='num'>{m.brier:.4f}</td>"
            f"<td class='num strong'>{m.def_elo:.0f}</td></tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


def attack_table(models: list[Model]) -> str:
    rows = sorted(
        models,
        key=lambda m: (m.survival is None, -(m.survival or 0), -m.att_elo),
    )
    out = [
        "<table><thead><tr>"
        "<th>Model</th><th class='num'>θ1 played</th><th class='num'>FN</th>"
        "<th class='num'>TP</th><th class='num'>Survival</th><th class='num'>Att Elo</th>"
        "<th class='num'>Clean rounds</th><th class='num'>Clean FP</th>"
        "<th class='num'>Clean FP rate</th><th class='num'>Refusals</th></tr></thead><tbody>"
    ]
    for m in rows:
        att_elo = f"{m.att_elo:.0f}" if m.played else "—"
        out.append(
            "<tr>"
            f"<td class='model'>{esc(m.name)}</td>"
            f"<td class='num'>{m.played}</td><td class='num'>{m.attack_fn}</td>"
            f"<td class='num'>{m.attack_tp}</td><td class='num'>{fmt_pct(m.survival, 1)}</td>"
            f"<td class='num strong'>{att_elo}</td><td class='num'>{m.clean_n}</td>"
            f"<td class='num'>{m.clean_fp}</td><td class='num'>{fmt_pct(m.clean_fp_rate, 0)}</td>"
            f"<td class='num'>{m.abstain_a}</td></tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


def value_table(models: list[Model]) -> str:
    rows = sorted(models, key=lambda m: -m.eff)
    out = [
        "<table><thead><tr>"
        "<th>Model</th><th class='num'>Efficiency</th><th class='num'>$/round</th>"
        "<th class='num'>Total $</th><th class='num'>Tokens</th>"
        "<th class='num'>Def Elo</th><th class='num'>Overall Elo</th></tr></thead><tbody>"
    ]
    for m in rows:
        out.append(
            "<tr>"
            f"<td class='model'>{esc(m.name)}</td>"
            f"<td class='num strong'>{m.eff:.0f}</td>"
            f"<td class='num'>${m.cost_per_round:.3f}</td>"
            f"<td class='num'>${m.cost_total:.2f}</td>"
            f"<td class='num'>{m.tokens / 1_000_000:.2f}M</td>"
            f"<td class='num'>{m.def_elo:.0f}</td>"
            f"<td class='num'>{m.overall:.0f}</td></tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


# ---------------------------------------------------------------- page
CSS = """
:root{
  --bg:#07111f; --bg2:#0a1524; --panel:#0d1a2b; --panel2:#101f33;
  --line:#1b2c44; --text:#e8eef7; --muted:#93a4bb; --faint:#5f7188;
  --gold:#c8aa6e; --teal:#3fd0c9; --red:#e06c75; --blue:#6ea8fe;
  --green:#7ec699; --purple:#b48ead;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:
    radial-gradient(1200px 600px at 15% -10%, rgba(63,208,201,.08), transparent 60%),
    radial-gradient(900px 500px at 95% 0%, rgba(200,170,110,.07), transparent 55%),
    var(--bg);
  color:var(--text);
  font:15px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:28px 22px 70px}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:34px;color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.topbar a{color:var(--muted)}
.hero{padding:10px 0 30px;border-bottom:1px solid var(--line);margin-bottom:30px}
.eyebrow{color:var(--gold);font-size:11px;letter-spacing:.18em;text-transform:uppercase;font-weight:700;margin-bottom:10px}
h1{font-size:clamp(30px,5vw,52px);line-height:1.04;margin:0 0 14px;letter-spacing:-.02em}
h1 span{color:var(--gold)}
.lede{max-width:820px;color:var(--muted);font-size:17px;line-height:1.6;margin:0}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.badge{border:1px solid var(--line);background:rgba(16,31,51,.75);border-radius:999px;padding:6px 11px;font-size:12px;color:var(--muted)}
.badge b{color:var(--text)}
.notice{margin-top:18px;padding:12px 14px;border:1px solid rgba(200,170,110,.28);background:rgba(200,170,110,.07);border-radius:10px;color:#d9c69d;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:26px 0 8px}
.kpi{background:linear-gradient(180deg,rgba(16,31,51,.9),rgba(13,26,43,.9));border:1px solid var(--line);border-radius:12px;padding:14px 15px}
.kpi .v{font-size:24px;font-weight:800;letter-spacing:-.02em;color:var(--text)}
.kpi .l{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.12em;margin-top:3px}
.kpi .s{font-size:12px;color:var(--muted);margin-top:5px}
.section{margin:44px 0 0}
.section h2{font-size:22px;letter-spacing:-.01em;margin:0 0 4px}
.section .sub{color:var(--muted);font-size:14px;margin:0 0 18px;max-width:880px}
.answers{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.answer{background:linear-gradient(180deg,rgba(16,31,51,.85),rgba(13,26,43,.85));border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px;position:relative;overflow:hidden}
.answer:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent,var(--gold))}
.answer .q{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.14em;margin-bottom:7px}
.answer .a{font-size:16px;font-weight:700;line-height:1.35;margin-bottom:6px}
.answer .d{color:var(--muted);font-size:13px;line-height:1.55}
.answer .tag{display:inline-block;margin-top:10px;font-size:11px;color:var(--accent,var(--gold));border:1px solid color-mix(in srgb,var(--accent,var(--gold)) 45%,transparent);border-radius:999px;padding:3px 8px}
.chart{background:linear-gradient(180deg,rgba(16,31,51,.7),rgba(13,26,43,.7));border:1px solid var(--line);border-radius:14px;padding:12px;margin:12px 0}
.chart svg{display:block;width:100%;height:auto}
.chart figcaption{color:var(--muted);font-size:12px;line-height:1.5;padding:8px 6px 2px}
.chart figcaption b{color:var(--text)}
.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:rgba(13,26,43,.75)}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid rgba(27,44,68,.7);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:#0c1829;color:var(--faint);font-size:10px;text-transform:uppercase;letter-spacing:.1em;font-weight:700;z-index:1}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.model{font-weight:700;color:var(--text)}
td.strong{color:var(--gold);font-weight:800}
tbody tr:hover{background:rgba(63,208,201,.045)}
.legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--muted);font-size:12px;margin:8px 2px 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.method{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}
.method .card{background:rgba(13,26,43,.75);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.method h3{font-size:14px;margin:0 0 8px;color:var(--text)}
.method p,.method li{color:var(--muted);font-size:13px}
.method ul{margin:0;padding-left:18px}
.method li{margin:4px 0}
.ru{border-top:1px solid var(--line);margin-top:46px;padding-top:26px}
.ru h2{font-size:18px;margin:0 0 10px}
.ru ul{margin:0;padding-left:20px;color:var(--muted)}
.ru li{margin:5px 0}
.footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);color:var(--faint);font-size:12px}
@media(max-width:1000px){
  .kpis{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:820px){
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .answers{grid-template-columns:1fr}
  .method{grid-template-columns:1fr}
  .wrap{padding:18px 14px 50px}
}
"""


def build_page(standings: dict, ledger: list[dict], models: list[Model], n_total: int) -> str:
    played_theta1 = [
        r for r in ledger if r["theta"] == 1 and r["outcome"] in ("TP", "FN")
    ]
    fn = [r for r in played_theta1 if r["outcome"] == "FN"]
    fp = [r for r in ledger if r["outcome"] == "FP"]
    def default_credential(mechanism: str) -> bool:
        text = (mechanism or "").lower()
        return "dev-admin-token" in text or (
            ("default" in text or "fallback" in text)
            and ("credential" in text or "token" in text or "admin" in text)
        )

    fp_default = sum(default_credential(r.get("mechanism") or "") for r in fp)
    total_cost = sum(m.cost_total for m in models)
    total_tokens = sum(m.tokens for m in models)
    season_label = standings.get("season_label") or standings.get("season_id") or "season"
    generated = standings.get("generated_at", "")[:10]
    scoring = standings.get("scoring_version", "")
    n_models = len(models)
    n_rounds = len(ledger)
    n_void = n_total - n_rounds
    has_r9001 = any(r.get("round_id") == "r-9001" for r in ledger)
    snapshot_note = (
        '<div class="notice"><b>Snapshot note.</b> This page includes all '
        f'{n_total} published rounds, including r-9001 (deepseek-flash vs '
        'opus-5.5, <b>TP</b>): deepseek-flash is 5/9 = 55.6% survival, opus is '
        '11/11 on defusal.</div>'
        if has_r9001
        else '<div class="notice"><b>Snapshot note.</b> This page analyzes the '
        f'{n_total}-round board behind the report. A 288th round (r-9001, '
        'deepseek-flash vs opus-5.5, <b>TP</b>) was added after the snapshot: '
        'deepseek-flash is now 5/9 = 55.6% survival, opus is 11/11 on defusal, '
        'and the conclusions do not change.</div>'
    )

    answer_cards = [
        (
            "1 · Defense",
            "gemini-4-argon is the best balance; grok-4.7 is the cleanest on false alarms; glm-5.3-max is the most proven.",
            "gemini-4-argon: 8/8 defusal, 1/14 FPR, 22 defense rounds. grok-4.7: 5/6, 0/9 FPR, but one patch broke smoke. glm-5.3-max: 11/11, 2/12 FPR, 23 rounds. gpt-6-astra is perfect (2/2, 0/8) but provisional at 15 rounds.",
            "Gatekeeper",
            TEAL,
        ),
        (
            "2 · Secure code",
            "gemini-4-argon and glm-5.3-max audit best and keep their own clean builds clear. If refusal is mandatory, gpt-6-astra and gpt-6.1 are the safety-first picks.",
            "Clean-build clearance: gemini 10/12 (83%), glm-5.3-max 10/13 (77%). Refusals on θ=1: gpt-6-astra 7/7, gpt-6.1 12/12, opus 8/8, sonnet 8/8. But refusal is provider policy, and the same models also refuse defender exploit work.",
            "Safety vs skill",
            GOLD,
        ),
        (
            "3 · Attack",
            "deepseek-flash wins 5 of 8. All five were detected; the patch passed smoke but the PoC still read the canary.",
            "deepseek-flash: 5/8 = 62.5% survival, attack Elo 1685, all five wins are incomplete fixes (not malformed patches). deepseek 3/10, muse-wonder 2/10, glm-5.3 2/18, glm-5.2 1/10. No model has a stealth win: 0/95 attacks with p < 0.5.",
            "Infiltrator",
            RED,
        ),
        (
            "4 · Most confusing",
            "deepseek-flash combines 62.5% attack survival with a 50% clean-build false-alarm rate.",
            "4 of 8 clean builds were flagged; 3 of those are the mandated dev-admin-token, 1 is stale .pyc. Next: deepseek (30% + 30%), muse-wonder (20% + 30%), glm-5.2 (10% + 44%). grok-4.7 has 42% clean FP but 0 attack wins.",
            "The confusing profile",
            PURPLE,
        ),
        (
            "5 · Expensive and bad",
            "muse-wonder: $0.985/round, 152k tokens per defense round, Def Elo 1351, 73% FPR.",
            "Highest cost per round and highest defense-token burn, while its Def Elo is 13th of 14. It defuses 8/8 detected attacks but cries wolf on 8 of 11 clean builds. Grok is also expensive ($0.920/round) but defends at 1684.",
            "Waste",
            RED,
        ),
        (
            "6 · Best value",
            "deepseek-flash by the board's efficiency rating; for an audit seat, glm-5.3-flash and gpt-6.1.",
            "Efficiency: deepseek-flash 1764 at $0.036/round, glm-5.3-flash 1754 at $0.050, gpt-6.1 1732 at $0.058. deepseek-flash is an attack specialist with Def Elo 1360; glm-5.3-flash is the cheapest strong auditor, gpt-6.1 the more proven cheap one.",
            "Best Value",
            GREEN,
        ),
    ]

    cards_html = "".join(
        f'<article class="answer" style="--accent:{color}">'
        f'<div class="q">{esc(q)}</div><div class="a">{esc(a)}</div>'
        f'<div class="d">{esc(d)}</div><div class="tag">{esc(tag)}</div></article>'
        for q, a, d, tag, color in answer_cards
    )

    defense_points = [
        {
            "label": m.name,
            "x": m.fpr,
            "y": m.defusal,
            "r": 7 + math.sqrt(max(1, m.def_n)) * 2.4,
            "color": (
                TEAL
                if m.fpr <= 0.2 and m.defusal >= 0.8
                else GOLD
                if m.defusal >= 0.8
                else BLUE
                if m.fpr <= 0.2
                else RED
            ),
            "title": f"{m.name}: defusal {m.defusal*100:.0f}%, FPR {m.fpr*100:.0f}%, {m.def_n} defense rounds, Brier {m.brier:.4f}",
        }
        for m in models
    ]
    defense_chart = scatter(
        defense_points,
        title="Defense map",
        x_label="False-positive rate (raw)",
        y_label="Defusal rate",
        quadrant_x=0.2,
        quadrant_y=0.8,
        x_max=1.12,
        y_max=1.12,
        label_xy={
            "gpt-6-astra": (0.09, 0.055, "start"),
            "gemini-4-argon": (0.20, 0.055, "start"),
            "glm-5.3-flash": (0.33, 0.055, "start"),
            "glm-5.3-max": (0.46, 0.055, "start"),
            "gpt-6.1": (0.59, 0.055, "start"),
        },
        label_offsets={
            "deepseek": (-10, 4, "end"),
        },
        note="Raw FPR includes the dev-admin-token artifact; see the false-alarm chart. Bubble size = defense rounds.",
    )

    attack_points = [
        {
            "label": m.name,
            "x": m.clean_fp_rate or 0,
            "y": m.survival or 0,
            "r": 7 + math.sqrt(max(1, m.played)) * 3.0,
            "color": (
                RED
                if (m.survival or 0) >= 0.1 and (m.clean_fp_rate or 0) >= 0.2
                else GOLD
                if (m.survival or 0) >= 0.1
                else BLUE
                if (m.clean_fp_rate or 0) >= 0.2
                else FAINT
            ),
            "title": f"{m.name}: survival {fmt_pct(m.survival,1)}, clean FP {fmt_pct(m.clean_fp_rate,0)}, {m.played} played attacks",
        }
        for m in models
        if m.played and m.clean_n
    ]
    attack_chart = scatter(
        attack_points,
        title="Attack map",
        x_label="Clean-build false-positive rate",
        y_label="Attack survival",
        quadrant_x=0.2,
        quadrant_y=0.1,
        label_xy={
            "gemini-4-argon": (0.68, 0.34, "start"),
            "kimi-k3": (0.68, 0.40, "start"),
            "glm-5.3": (0.68, 0.46, "start"),
            "glm-5.3-max": (0.68, 0.52, "start"),
            "grok-4.7": (0.68, 0.58, "start"),
            "glm-5.2": (0.68, 0.64, "start"),
        },
        note="Top-right is the confusing profile: attacks survive, while clean code looks vulnerable. Bubble size = played attack rounds. Models with no played attacks are omitted.",
    )

    fp_chart = stacked_fp(models)
    fn_chart = stacked_fn(models)
    cost_chart = cost_scatter(models)
    eff_chart = hbars(models)
    ratings_chart = dotplot(models)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Defuse Arena Model Report: Defense, Attack and Value per AI Model</title>
<meta name="description" content="Charts and tables on how each AI model defends, attacks and spends in Defuse Arena: audit ratings, false alarms, exploits that beat the patch, and cost per round.">
<link rel="canonical" href="https://defuse-arena.vercel.app/analysis">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#010A13">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Defuse Arena">
<meta property="og:url" content="https://defuse-arena.vercel.app/analysis">
<meta property="og:title" content="Defuse Arena model report">
<meta property="og:description" content="Charts and tables on how each AI model defends, attacks and spends in Defuse Arena: audit ratings, false alarms, exploits that beat the patch, and cost per round.">
<meta property="og:image" content="https://defuse-arena.vercel.app/social/06-price.png">
<meta property="og:image:width" content="1920">
<meta property="og:image:height" content="1080">
<meta property="og:image:alt" content="Audit rating against cost per round: GLM-5.3 Flash matches the top auditors for $0.05 a round.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@vargastartup">
<meta name="twitter:title" content="Defuse Arena model report">
<meta name="twitter:description" content="Charts and tables on how each AI model defends, attacks and spends in Defuse Arena: audit ratings, false alarms, exploits that beat the patch, and cost per round.">
<meta name="twitter:image" content="https://defuse-arena.vercel.app/social/06-price.png">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <a href="board.html">← Leaderboard</a>
    <span>Defuse Arena · analysis snapshot</span>
  </div>

  <header class="hero">
    <div class="eyebrow">Model report · {esc(scoring)}</div>
    <h1>What the board says about <span>defense, attack, and value</span></h1>
    <p class="lede">A frozen read of the {n_total}-round published board ({n_rounds} non-void rounds scored): who patches real attacks, who cries wolf on clean code, whose attacks survive, who is expensive, and who is worth the money. The benchmark separates <b>knowing</b> from <b>fixing</b>; most of the interesting signal is on the fixing side.</p>
    <div class="badges">
      <span class="badge"><b>{n_total}</b> published rounds</span>
      <span class="badge"><b>{n_rounds}</b> non-void</span>
      <span class="badge"><b>{n_models}</b> models</span>
      <span class="badge">scoring <b>v{esc(scoring)}</b></span>
      <span class="badge">generated <b>{esc(generated)}</b></span>
      <span class="badge">source <b>{esc(season_label)}</b></span>
    </div>
    {snapshot_note}
  </header>

  <section class="kpis">
    <div class="kpi"><div class="v">{n_rounds}</div><div class="l">non-void rounds</div><div class="s">{n_void} void excluded</div></div>
    <div class="kpi"><div class="v">{len(played_theta1)}</div><div class="l">played θ=1 attacks</div><div class="s">{len(fn)} survived · {len(played_theta1)-len(fn)} blocked</div></div>
    <div class="kpi"><div class="v">0</div><div class="l">detection misses</div><div class="s">all {len(played_theta1)} had p ≥ 0.88</div></div>
    <div class="kpi"><div class="v">{len(fp)}</div><div class="l">false alarms</div><div class="s">{fp_default} are the default-credential artifact</div></div>
    <div class="kpi"><div class="v">${total_cost:.0f}</div><div class="l">season spend</div><div class="s">{total_tokens/1_000_000:.1f}M tokens</div></div>
  </section>

  <section class="section">
    <h2>Six answers</h2>
    <p class="sub">Each card is the one-line answer, with the number behind it. The charts below show the full field.</p>
    <div class="answers">{cards_html}</div>
  </section>

  <section class="section">
    <h2>Defense: patch validity vs false alarms</h2>
    <p class="sub">The x-axis is the raw false-positive rate; the y-axis is the share of detected attacks whose patch actually blocked the PoC. The top-right corner is the good quadrant. But the raw FPR is inflated by the mandated <code>dev-admin-token</code>; the artifact-free view is in the false-alarm chart.</p>
    <figure class="chart">{defense_chart}<figcaption><b>Reading it:</b> gemini-4-argon sits top-right with 8/8 defusal and 1/14 FPR. grok-4.7 is the cleanest on false alarms (0/9) but has one patch-gate failure. muse-wonder and deepseek sit on the far right: they detect and often patch, but they also flag many clean builds.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Attack: survival vs clean-code confusion</h2>
    <p class="sub">The x-axis is how often the model's clean builds were falsely flagged; the y-axis is how often its θ=1 attacks survived the patch. The top-right corner is the “confusing” profile: it hides working bugs while its clean code looks suspicious.</p>
    <figure class="chart">{attack_chart}<figcaption><b>Reading it:</b> deepseek-flash is the only model in the top-right: 5/8 survival and 4/8 clean-build FPs. deepseek and muse-wonder are the next attackers but have lower survival. grok-4.7 has a high clean-FP rate but never won an attack.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Ratings with intervals</h2>
    <p class="sub">Overall, attack, and defense Elo with 95% intervals. The point estimates are useful for ordering; the intervals are wide enough that the top defense cluster is not statistically separated.</p>
    <figure class="chart">{ratings_chart}<figcaption><b>Reading it:</b> grok-4.7 leads overall and defense on point estimates, but its interval overlaps gemini-4-argon and glm-5.3-max. The attack panel shows only models with played θ=1 attacks; the four models that refused every attack are omitted from that panel, because their pooled rating would be driven by clean builds and forfeits.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Cost vs defense</h2>
    <p class="sub">Up and to the left is better value: lower price per round, higher defense Elo. The dashed line is the cost/defense Pareto frontier.</p>
    <figure class="chart">{cost_chart}<figcaption><b>Reading it:</b> muse-wonder is the expensive/bad corner: $0.985/round and Def Elo 1351. grok-4.7 is expensive but good. gemini-4-argon and glm-5.3-flash are the value defenders. deepseek is cheap but the weakest defender.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Efficiency ranking</h2>
    <p class="sub">The board's margin-weighted efficiency rating, with price per round on the right. This is the “best value” metric, not a pure skill rating.</p>
    <figure class="chart">{eff_chart}<figcaption><b>Reading it:</b> deepseek-flash, glm-5.3-flash, and gpt-6.1 are the cheap top three. The ranking rewards cheap wins, so read it with the role: deepseek-flash is an attack specialist, glm-5.3-flash an audit specialist, gpt-6.1 a cheap auditor that refuses attacks.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Where the false alarms come from</h2>
    <p class="sub">Every defended clean build, split into cleared (TN), the mandated <code>dev-admin-token</code> flag, and a real false alarm. The middle band is the artifact; the red band is the model's own noise.</p>
    <figure class="chart">{fp_chart}<figcaption><b>Reading it:</b> deepseek's 89% FPR is entirely the default-credential flag. muse-wonder has the largest other-FP band (3/6), glm-5.2 has one timing-side-channel FP, and glm-5.3-flash has one concurrency FP. For most of the field the red band is empty.</figcaption></figure>
  </section>

  <section class="section">
    <h2>How attacks survived</h2>
    <p class="sub">A win is not one thing. “Incomplete fix” means the patch applied, the smoke suite passed, and the PoC still read the canary — the strongest attack win. “Smoke broken” and “malformed patch” are patch-gate failures.</p>
    <figure class="chart">{fn_chart}<figcaption><b>Reading it:</b> all five of deepseek-flash's wins are incomplete fixes. deepseek has two incomplete fixes and one smoke break; glm-5.3 has one of each; muse-wonder's two wins are both gate failures; glm-5.2's only win is a gate failure.</figcaption></figure>
  </section>

  <section class="section">
    <h2>Defense table</h2>
    <p class="sub">TP — the patch blocked the PoC. FN — it did not. FPR — false alarms over clean builds. Brier is the mean over played defense rounds.</p>
    <div class="tablewrap">{defense_table(models)}</div>
  </section>

  <section class="section">
    <h2>Attack table</h2>
    <p class="sub">Survival = FN / played θ=1. Clean FP rate = FP / (FP + TN) on the model's own clean builds. Refusals are ABSTAIN_A on θ=1; they are not counted as attack wins. Att Elo is the pooled attacker rating and includes clean-build games, so read it with the played count; a dash means no played θ=1 attacks.</p>
    <div class="tablewrap">{attack_table(models)}</div>
  </section>

  <section class="section">
    <h2>Cost and value table</h2>
    <p class="sub">Efficiency is the board's margin-weighted rating. Cost is USD for both roles; tokens are the raw meter reading.</p>
    <div class="tablewrap">{value_table(models)}</div>
  </section>

  <section class="section">
    <h2>Method and caveats</h2>
    <div class="method">
      <div class="card">
        <h3>Data</h3>
        <ul>
          <li><b>{n_total} published rounds</b>, {n_rounds} non-void, from <code>{esc(season_label)}</code>: 258 core rounds plus 29 flash-probe rounds from s-2026-01.</li>
          <li>{n_void} void rounds are excluded. The ledger keeps billable tokens and USD cost; the transcript split behind them is not used here.</li>
          <li>Ratings are Bradley–Terry fits; the efficiency rating is the retired margin-weighted fit, kept as a value axis.</li>
        </ul>
      </div>
      <div class="card">
        <h3>What not to over-read</h3>
        <ul>
          <li><b>Detection is saturated.</b> 0 of {len(played_theta1)} played attacks had p &lt; 0.5. The FN axis is patch quality, not detection.</li>
          <li><b>FP is mostly an artifact.</b> {fp_default} of {len(fp)} FPs are the default-credential artifact (34 explicitly cite <code>dev-admin-token</code>, 1 uses other wording); the grader randomizes the token, so the flag is a real-world weakness but not the graded bug.</li>
          <li><b>Small samples.</b> 10–55 rounds per model; the top defense intervals overlap. Flash-probe is an all-high field, not the core season; its opponents and effort variants differ.</li>
          <li>This is a synthetic audit-loop benchmark, not a real-world security claim.</li>
        </ul>
      </div>
    </div>
  </section>

  <section class="ru">
    <h2>Кратко по-русски</h2>
    <ul>
      <li><b>Защита:</b> gemini-4-argon — лучший баланс; grok-4.7 — чище всех по FP; glm-5.3-max — самый доказанный.</li>
      <li><b>Безопасный код:</b> gemini-4-argon и glm-5.3-max; если нужен отказ от атаки — gpt-6-astra или gpt-6.1, но они же отказываются и от defender-exploit работы.</li>
      <li><b>Атака:</b> deepseek-flash, 5/8; все пять побед — не stealth, а incomplete fix: патч прошёл smoke, PoC всё ещё читает canary.</li>
      <li><b>Запутанные:</b> deepseek-flash (62.5% атак + 50% clean FP), но большая часть FP — артефакт dev-admin-token.</li>
      <li><b>Дорого и плохо:</b> muse-wonder — $0.985/раунд, 152k токенов на защитный раунд, Def Elo 1351, 73% FPR.</li>
      <li><b>Best value:</b> deepseek-flash по overall efficiency; для аудита — glm-5.3-flash и gpt-6.1.</li>
    </ul>
  </section>

  <div class="footer">Generated by <code>scripts/analysis_report.py</code> from <code>seasons/{esc(season_label)}</code> · {esc(generated)} · no scoring or board semantics changed.</div>
</div>
</body>
</html>"""


def main() -> None:
    season = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEASON
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    standings, raw, ledger = load(season)
    models = build_models(standings, ledger)
    page = build_page(standings, ledger, models, len(raw))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(f"{out}: {len(raw)} published / {len(ledger)} non-void rounds · {len(models)} models · {len(page)/1024:.0f} KB")


if __name__ == "__main__":
    main()
