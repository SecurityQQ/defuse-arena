#!/usr/bin/env python3
"""Render the article's link-preview cards from the champions on the page.

Wick and Lumen are read out of web/index.html (the shared <defs> and the two
hero drawings), so the preview always matches the article. Writes, under
web/social/:

  og-champions.png        1200x630   og:image and twitter:image (1.91:1)
  og-champions-16x9.png   1200x675   JSON-LD Article image
  og-champions-4x3.png    1200x900   JSON-LD Article image
  og-champions-1x1.png    1200x1200  JSON-LD Article image

Everything important sits in the inner 1080x510 and in the centre square,
because X trims the sides toward 16:9 and iMessage and Slack crop to squares.
Rendering uses the local Chrome in headless mode; set CHROME to override.

    python3 scripts/og_card.py
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "index.html"
OUT = ROOT / "web" / "social"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SIZES = [("og-champions", 1200, 630), ("og-champions-16x9", 1200, 675),
         ("og-champions-4x3", 1200, 900), ("og-champions-1x1", 1200, 1200)]

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Rajdhani:wght@600;700&family=Spectral:ital,wght@1,400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0}
html,body{width:var(--w);height:var(--h);overflow:hidden;background:#010A13}
.card{position:relative;width:100%;height:100%;overflow:hidden;color:#F0E6D2;font-family:Rajdhani,sans-serif;
  background:radial-gradient(60% 70% at 50% 108%,rgba(10,200,185,.20),transparent 70%),
    radial-gradient(45% 60% at 8% 30%,rgba(10,200,185,.16),transparent 70%),
    radial-gradient(45% 60% at 92% 30%,rgba(255,107,107,.17),transparent 70%),
    linear-gradient(180deg,#06101F 0%,#010A13 100%)}
.hex{position:absolute;inset:0;opacity:.07;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='98'%3E%3Cpath d='M28 66L0 50V17L28 1l28 16v33L28 66zm0 32V66' fill='none' stroke='%23C8AA6E' stroke-width='1.2'/%3E%3C/svg%3E");background-size:56px 98px}
.floor{position:absolute;left:50%;bottom:-42%;width:130%;height:70%;transform:translateX(-50%);border-radius:50%;
  border:2px solid rgba(200,170,110,.35);box-shadow:0 0 60px rgba(10,200,185,.18) inset,0 0 0 18px rgba(200,170,110,.05)}
.frame{position:absolute;inset:18px;border:1px solid rgba(200,170,110,.35);border-radius:6px}
.frame::before{content:"";position:absolute;inset:6px;border:1px solid rgba(200,170,110,.12);border-radius:4px}
.champ{position:absolute;bottom:calc(var(--h)*.06);height:calc(var(--h)*.78);filter:drop-shadow(0 18px 30px rgba(0,0,0,.6))}
.champ svg{height:100%;width:auto;display:block;overflow:visible}
.lumen{left:calc(var(--w)*.03)} .wick{right:calc(var(--w)*.03)}
.lumen{filter:drop-shadow(0 0 40px rgba(10,200,185,.35)) drop-shadow(0 18px 30px rgba(0,0,0,.6))}
.wick{filter:drop-shadow(0 0 40px rgba(255,107,107,.35)) drop-shadow(0 18px 30px rgba(0,0,0,.6))}
.mid{position:absolute;left:50%;top:50%;transform:translate(-50%,-52%);width:min(640px,calc(var(--w)*.56));text-align:center}
.kicker{font:700 19px/1 Rajdhani;letter-spacing:.32em;text-transform:uppercase;color:#C8AA6E}
.crest{display:block;width:34px;height:34px;margin:0 auto 18px;filter:drop-shadow(0 0 12px rgba(10,200,185,.6))}
h1{margin-top:16px;font:900 88px/.95 Cinzel;letter-spacing:.04em;text-transform:uppercase;
  background:linear-gradient(180deg,#FFF8E8 0%,#F0E6D2 30%,#C8AA6E 62%,#7A5C28 100%);-webkit-background-clip:text;background-clip:text;color:transparent;
  filter:drop-shadow(0 6px 22px rgba(0,0,0,.8))}
.q{margin-top:20px;font:italic 400 31px/1.25 Spectral;color:#E2D8C0}
.div{display:flex;align-items:center;gap:12px;justify-content:center;margin:24px auto 0;width:70%}
.div::before,.div::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(200,170,110,.7),transparent)}
.div i{width:9px;height:9px;transform:rotate(45deg);border:1px solid #C8AA6E}
.stats{display:flex;justify-content:center;gap:0;margin-top:24px}
.stats div{padding:0 22px;border-left:1px solid rgba(200,170,110,.3)}
.stats div:first-child{border-left:0}
.stats b{display:block;font:700 40px/1 Cinzel;color:#F0E6D2}
.stats b.ok{color:#4FE0B0}.stats b.hot{color:#FF6B6B}
.stats span{display:block;margin-top:8px;font:700 14px/1.15 Rajdhani;letter-spacing:.16em;text-transform:uppercase;color:#8DA0B8}
.url{position:absolute;left:0;right:0;bottom:calc(var(--h)*.065);text-align:center;font:700 16px/1 Rajdhani;letter-spacing:.3em;text-transform:uppercase;color:#C8AA6E}
.tag{position:absolute;bottom:calc(var(--h)*.02);font:700 13px/1 Cinzel;letter-spacing:.24em;text-transform:uppercase}
/* tall formats: characters shrink to the bottom corners, text moves up */
.tall .champ{height:calc(var(--h)*.5)}
.tall .mid{top:40%;width:calc(var(--w)*.86)}
.tall h1{font-size:104px}
.sq .mid{top:36%}
.sq .champ{height:calc(var(--h)*.42)}
.sq .lumen{left:calc(var(--w)*.04)} .sq .wick{right:calc(var(--w)*.04)}
</style></head><body><div class="card" id="card">DEFS
<div class="hex"></div><div class="floor"></div><div class="frame"></div>
<div class="champ lumen">LUMEN</div><div class="champ wick">WICK</div>
<div class="mid">
  <svg class="crest" viewBox="0 0 30 30"><path d="M15 1 29 15 15 29 1 15Z" fill="none" stroke="#C8AA6E"/><path d="M15 8 22 15 15 22 8 15Z" fill="#0AC8B9"/></svg>
  <div class="kicker">288 rounds · 14 AI models</div>
  <h1>Defuse<br>Arena</h1>
  <p class="q">Which AI model audits code best?</p>
  <div class="div"><i></i></div>
  <div class="stats">
    <div><b class="ok">96/96</b><span>bugs found</span></div>
    <div><b class="hot">31%</b><span>false alarms</span></div>
    <div><b class="hot">46</b><span>rounds refused</span></div>
  </div>
</div>
<div class="url">defuse-arena.vercel.app</div>
</div>
<script>
const p=new URLSearchParams(location.search),w=+p.get("w")||1200,h=+p.get("h")||630;
document.documentElement.style.setProperty("--w",w+"px");document.documentElement.style.setProperty("--h",h+"px");
if(h/w>0.7)document.getElementById("card").classList.add("tall");
if(h/w>0.95)document.getElementById("card").classList.add("sq");
</script></body></html>"""


def card_html(page: str) -> str:
    defs = re.search(r'(<svg width="0".*?</svg>)', page, re.S).group(1)
    lumen = re.search(r'<div class="champ lumen".*?(<svg viewBox.*?</svg>)', page, re.S).group(1)
    wick = re.search(r'<div class="champ wick".*?(<svg viewBox.*?</svg>)', page, re.S).group(1)
    html = TEMPLATE.replace("DEFS", defs).replace("LUMEN", lumen).replace("WICK", wick)
    # a still: freeze the idle loops on their first frame
    return html.replace("<style>", "<style>.bob,.halo,.cape,.tail,.spark,.blink,.flame{animation:none!important}", 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "card.html"
        src.write_text(card_html(PAGE.read_text()))
        for name, w, h in SIZES:
            dest = OUT / f"{name}.png"
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={w},{h}", "--virtual-time-budget=4000",
                            f"--screenshot={dest}", f"file://{src}?w={w}&h={h}"],
                           check=True, capture_output=True)
            print(f"{dest.relative_to(ROOT)}  {w}x{h}")


if __name__ == "__main__":
    main()
