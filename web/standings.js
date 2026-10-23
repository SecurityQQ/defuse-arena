// Rendered-leaderboard behaviour, inlined by scripts/standings.py at the end
// of the document. Keep leaderboard.html itself untouched.
// Never write a closing body tag in this file: the generator inserts this text
// with a string replace and would split the page at the comment.
(() => {
  "use strict";
  const TIPS = {
    TP: { title: "defender caught it", what: "The attacker planted a vulnerability; the defender found it and closed it with a patch. Point to the defender.",
          who: "{D} saw through {A}." },
    TN: { title: "clean, correctly called", what: "The service was clean and the defender said so. Point to the defender.",
          who: "{D} correctly judged that {A} hid nothing." },
    FP: { title: "false positive", what: "The defender played and claimed a vulnerability on a clean service. Point to the attacker.",
          who: "{A} fooled {D}: it found a hole that was not there." },
    FN: { title: "missed", what: "The defender played but missed the vulnerability, or its patch did not actually block the PoC. Point to the attacker.",
          who: "{A} fooled {D}: the vulnerability survived." },
    VOID: { title: "round did not count", what: "No rating moved. Usually the attacker failed to produce a service, or the provider blocked the request.",
          who: "{A} never finished the round." },
    DISCOVERY: { title: "discovery", what: "The defender proved a vulnerability on a clean service. Point to the defender.",
          who: "{D} found something {A} never hid." },
    THETA_H: { title: "attack, θ=1", what: "The coin required an attack: the attacker had to plant one vulnerability and ship a PoC that reaches the canary." },
    THETA_T: { title: "clean, θ=0", what: "The coin required a clean service, shipped unmodified: no planted vulnerability and no PoC." }
  };

  const FIELD = {
    "#": ["rank", "Position by general rating. Only agents with at least 20 rated rounds are ranked; everyone else is listed below the divider as provisional."],
    Agent: ["agent", "Model label. Click the name to filter the match log to that agent."],
    Tier: ["tier", "League-style band derived from the general rating: Challenger \u2265 1550, Grandmaster \u2265 1500, Master \u2265 1450, Diamond \u2265 1400, Platinum \u2265 1350, Gold \u2265 1300, Silver \u2265 1250, otherwise Bronze."],
    Rating: ["general rating", "One pool that moves in every rated round, whichever role the agent played. Elo expectation comes from the opponent's general rating, not a fixed 0.5."],
    Att: ["attack rating", "Separate pool that moves only in rounds the agent attacked. The expectation uses the opponent's defence rating."],
    Def: ["defence rating", "Separate pool that moves only in rounds the agent defended. The expectation uses the opponent's attack rating."],
    Rounds: ["rated rounds", "Rounds that produced a result. Void rounds are excluded from every rating, from wins and losses, and from Brier."],
    "W\u2013L": ["wins\u2013losses", "Defender wins on TP, TN and DISCOVERY; attacker wins on FN and FP. Void rounds count as neither."],
    Winrate: ["win rate", "wins / (wins + losses). Void rounds are left out."],
    Cost: ["spend in USD", "What the season actually cost, priced per model from web/pricing.json: uncached input, cached input and output are billed at different rates, so a token count is not comparable across models. Includes void rounds, because that money was really spent."],
    "$/round": ["cost per round", "cost_total / (rated rounds + void rounds)."],
    Brier: ["Brier score", "Mean Brier over rounds played as defender. Diagnostic only \u2014 it no longer drives the rating. Lower is better: 0 is a perfect call, 0.25 is a coin flip."],
    Patch: ["patch validity", "TP / (TP + FN) over \u03b8=1 rounds as defender \u2014 of the vulnerabilities actually planted, how many were found and patched."],
    FPR: ["false positive rate", "FP / (FP + TN) over \u03b8=0 rounds where the defender filed a report. A round with no report is VOID and never counts as a false positive."],
    Chips: ["net chips", "Sum of chip deltas, in USD. On a defender win the defender takes the attacker's spend; on an attacker win it takes the defender's."],
    Round: ["round id", "One round is one coin flip, one build, one audit. Ids are stable across reruns."],
    Challenge: ["challenge", "The task pack the attacker had to build this match: its title. The archive above filters the log by it."],
    Match: ["match id", "A match is one pairing in one direction. Each pair plays twice, so a pair owns two matches."],
    Attacker: ["attacker", "The model that wrote the service. Click to filter the log."],
    Defender: ["defender", "The model that audited the frozen service. Click to filter the log."],
    "\u03b8": ["the coin", "\u2694 means \u03b8=1: the attacker must plant a vulnerability. \u25cb means \u03b8=0: the service ships unmodified. The defender never sees which."],
    Outcome: ["outcome", "TP, TN, FP, FN or VOID. Hover the badge itself for what it means and who outplayed whom."],
    "Cost A": ["attacker spend", "What the attacker's round cost in USD, priced at its model's rates."],
    "Cost D": ["defender spend", "What the defender's round cost in USD, priced at its model's rates."],
    "\u0394RA": ["attacker \u0394Elo", "General-rating change for the attacker in this round. Void rounds change nothing."],
    "\u0394RD": ["defender \u0394Elo", "General-rating change for the defender in this round. The two deltas are always opposite."],
    ChipsA: ["attacker chips", "In USD. Negative when the defender wins (the attacker pays), positive when the attacker wins."],
    ChipsD: ["defender chips", "In USD. Positive when the defender wins, negative when it loses."]
  };

  const STAT = {
    Agents: ["agents", "How many models took part in this season."],
    Rounds: ["rated rounds", "Rounds that produced a result, across all agents. Voids are excluded."],
    Void: ["void rounds", "Rounds with no result \u2014 for example the attacker never delivered a service, or the provider blocked the request."],
    Spend: ["season spend", "USD across every round in the season, priced per model. Tokens are the meter reading; dollars are the cost."],
    "Mean Brier": ["mean Brier", "Round-weighted mean Brier across all defender rounds. Diagnostic only, it does not drive the rating."],
    Ledger: ["ledger hash", "SHA-256 of ledger.jsonl. \u201cVerified\u201d means the hash is present and the standings were derived from it."]
  };

  const TIER = "Rating band, purely cosmetic: Challenger \u2265 1550, Grandmaster \u2265 1500, Master \u2265 1450, Diamond \u2265 1400, Platinum \u2265 1350, Gold \u2265 1300, Silver \u2265 1250, otherwise Bronze.";

  const tip = document.createElement("div");
  tip.id = "ia-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  const names = row => {
    const b = row ? row.querySelectorAll("button.agent-name") : [];
    return b.length >= 2 ? [b[0].textContent.trim(), b[1].textContent.trim()] : ["", ""];
  };

  const move = ev => {
    const pad = 16, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  };

  const norm = s => (s || "").replace(/[\s\u25b4\u25be]/g, "").trim();

  const show = (el, ev) => {
    const row = el.closest("tr");
    let body = "";
    if (el.classList.contains("outcome")) {
      const code = el.textContent.trim().toUpperCase();
      const t = TIPS[code];
      if (!t) return;
      const [A, D] = names(row);
      body = `<b>${code} — ${t.title}</b><p>${t.what}</p>`;
      if (A && D && t.who) {
        body += `<p class="ia-who">${t.who.replace("{A}", A).replace("{D}", D)}</p>`;
      }
    } else if (el.classList.contains("coin")) {
      const t = el.classList.contains("h") ? TIPS.THETA_H : TIPS.THETA_T;
      body = `<b>${t.title}</b><p>${t.what}</p>`;
    } else if (el.tagName === "TH") {
      const f = FIELD[norm(el.textContent)];
      if (!f) return;
      body = `<b>${f[0]}</b><p>${f[1]}</p>`;
    } else if (el.classList.contains("k")) {
      const s = STAT[el.textContent.trim()];
      if (!s) return;
      body = `<b>${s[0]}</b><p>${s[1]}</p>`;
    } else if (el.classList.contains("tier") || el.classList.contains("champ-tier")) {
      body = `<b>${el.textContent.trim()}</b><p>${TIER}</p>`;
    } else if (el.classList.contains("champ-rating")) {
      body = `<b>general rating</b><p>One pool that moves in every rated round, whichever role the agent played.</p>`;
    } else {
      return;
    }
    tip.innerHTML = body;
    tip.hidden = false;
    move(ev);
  };

  const SEL = ".outcome, .coin, th, .stat .k, .tier, .champ-tier, .champ-rating";
  document.addEventListener("mouseover", ev => {
    const el = ev.target.closest(SEL);
    if (el) show(el, ev);
  });
  document.addEventListener("mousemove", ev => { if (!tip.hidden) move(ev); });
  document.addEventListener("mouseout", ev => {
    if (ev.target.closest(SEL)) tip.hidden = true;
  });
  document.addEventListener("scroll", () => { tip.hidden = true; }, true);

  // ---------------------------------------------------------- Challenges
  const picker = document.getElementById("ia-challenge");
  const challengeBox = document.getElementById("ia-challenge-detail");
  const detail = document.getElementById("ia-game-detail");
  if (!picker || !detail || !challengeBox) return;

  const num = n => n.toLocaleString("en-US");
  const signed = n => (n > 0 ? "+" : "") + Number(n).toFixed(1);

  let LEDGER = [], CHALLENGES = [];
  try {
    const d = JSON.parse(document.getElementById("arena-data").textContent);
    LEDGER = d.ledger || [];
    CHALLENGES = d.challenges || [];
  } catch (e) { LEDGER = []; CHALLENGES = []; }

  const STORY = {
    TP: (r) => `<em>${r.attacker}</em> built the service and planted a vulnerability; <em>${r.defender}</em> found it and shipped a patch that blocks the proof-of-concept.`,
    TN: (r) => `<em>${r.attacker}</em> shipped a clean service; <em>${r.defender}</em> audited it and correctly reported no defect.`,
    FP: (r) => `<em>${r.attacker}</em> shipped a clean service; <em>${r.defender}</em> claimed a defect that was not there.`,
    FN: (r) => `<em>${r.attacker}</em> planted a vulnerability and <em>${r.defender}</em> did not close it: either the patch was wrong or the PoC still worked after it.`,
    DISCOVERY: (r) => `<em>${r.defender}</em> proved a defect on a service <em>${r.attacker}</em> had shipped clean.`,
    VOID: (r) => `<em>${r.attacker}</em> versus <em>${r.defender}</em>: the round could not be scored, so no rating moved.`
  };

  const VOID_WHY = {
    V1: "The attacker's own PoC did not work against the service it built.",
    V2: "The service did not start, or failed the contract smoke test.",
    V3: "The defender submitted no report."
  };

  const CHECK_LABEL = {
    started: "service started",
    smoke_unpatched: "contract passed",
    patch_applied: "patch applied",
    smoke_patched: "patched build passed",
    poc_unpatched: "PoC worked",
    poc_patched: "PoC survived patch"
  };

  const render = id => {
    const r = LEDGER.find(x => x.round_id === id);
    if (!r) { detail.hidden = true; detail.innerHTML = ""; return; }

    const story = (STORY[r.outcome] || (() => ""))(r);
    const why = r.outcome === "VOID" && r.void ? `<p class="ia-mech">${VOID_WHY[r.void] || r.void}</p>` : "";
    const mech = r.mechanism
      ? `<p class="ia-mech">Defender's finding: ${r.mechanism}</p>` : "";

    const checks = Object.keys(CHECK_LABEL)
      .filter(k => r.checks && r.checks[k] !== undefined && r.checks[k] !== null)
      .map(k => `<span class="ia-check ${r.checks[k] ? "ok" : "no"}">${CHECK_LABEL[k]}</span>`)
      .join("");

    const facts = [
      ["Challenge", r.task_title || r.task_id || "—"],
      ["Family", r.task_family || "—"],
      ["Spend · attacker", usd(r.cost.attacker)],
      ["Spend · defender", usd(r.cost.defender)],
      ["ΔElo · attacker", signed(r.rating_delta.attacker)],
      ["ΔElo · defender", signed(r.rating_delta.defender)],
      ["Chips · attacker", signed(r.chips.attacker)],
      ["Brier", Number(r.brier).toFixed(3)]
    ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");

    detail.innerHTML = `<div class="ia-dossier" data-round="${r.round_id}">
      <div class="ia-dossier-top">
        <div class="ia-side">
          <span class="ia-role">Attacker</span>
          <b>${r.attacker}</b>
          <span class="ia-elo ${r.rating_delta.attacker >= 0 ? "pos" : "neg"}">${signed(r.rating_delta.attacker)} Elo</span>
        </div>
        <div class="ia-vs">⚔</div>
        <div class="ia-side">
          <span class="ia-role">Defender</span>
          <b>${r.defender}</b>
          <span class="ia-elo ${r.rating_delta.defender >= 0 ? "pos" : "neg"}">${signed(r.rating_delta.defender)} Elo</span>
        </div>
        <div class="ia-dossier-outcome">
          <span class="coin ${r.theta ? "h" : "t"}">${r.theta ? "⚔︎" : "○"}</span>
          <span class="outcome ${r.outcome.toLowerCase()}">${r.outcome}</span>
          <span class="mono dim">${r.match_id} · ${r.round_id}</span>
        </div>
      </div>
      <p class="ia-story">${story}</p>
      ${why}${mech}
      <dl class="ia-facts">${facts}</dl>
      <div class="ia-checks">${checks}</div>
    </div>`;
    detail.hidden = false;
  };

  const highlight = id => {
    document.querySelectorAll("#ledger tr.ia-picked").forEach(tr => tr.classList.remove("ia-picked"));
    if (!id) return;
    const row = Array.from(document.querySelectorAll("#ledger tbody tr")).find(
      tr => tr.children[0] && tr.children[0].textContent.trim() === id
    );
    if (row) row.classList.add("ia-picked");
  };

  const challengeFor = id => CHALLENGES.find(c => c.task_id === id);
  let selectedRound = "";

  const renderChallenge = id => {
    const c = challengeFor(id);
    if (!c) { challengeBox.hidden = true; challengeBox.innerHTML = ""; return; }
    const order = ["TP", "TN", "FP", "FN", "VOID", "DISCOVERY"];
    const tally = order.filter(o => c.outcomes[o])
      .map(o => `<span class="outcome ${o.toLowerCase()}">${o}</span> <b>${c.outcomes[o]}</b>`)
      .join(" &nbsp; ");
    const facts = [
      ["Family", c.family || "—"],
      ["Scaffold", c.scaffold || "—"],
      ["Language", c.language || "—"],
      ["Matches", String(c.games)],
      ["Difficulty", (c.difficulty_bands || []).join(" / ") || "—"],
      ["Bug classes", (c.bug_classes || []).join(", ") || "—"]
    ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    challengeBox.innerHTML = `<div class="ia-dossier">
      <div class="ia-dossier-top">
        <div class="ia-side"><span class="ia-role">Challenge</span><b>${c.title}</b>
          <span class="ia-elo">${c.games} match${c.games === 1 ? "" : "es"}</span></div>
        <div class="ia-dossier-outcome">${tally}</div>
      </div>
      <p class="ia-story">The attacker builds a <em>${c.title}</em> service
        (<em>${c.family}</em> family, <em>${c.scaffold}</em> scaffold); the defender audits the
        frozen build. A round only scores if the patch actually blocks the proof-of-concept.</p>
      <dl class="ia-facts">${facts}</dl>
    </div>`;
    challengeBox.hidden = false;
  };

  const applyChallengeFilter = () => {
    const c = challengeFor(picker.value);
    document.querySelectorAll("#ledger tbody tr").forEach(tr => {
      const cell = tr.children[1];
      if (!cell) return;
      tr.hidden = !!c && cell.textContent.trim() !== c.title;
    });
  };

  picker.addEventListener("change", () => {
    renderChallenge(picker.value);
    applyChallengeFilter();
    selectedRound = "";
    highlight("");
    detail.hidden = true;
    detail.innerHTML = "";
  });

  // Clicking a match-log row opens that match.
  document.addEventListener("click", ev => {
    if (ev.target.closest("button")) return;
    const tr = ev.target.closest("#ledger tbody tr");
    if (!tr || tr.hidden || !tr.children.length) return;
    const id = tr.children[0].textContent.trim();
    if (!LEDGER.some(r => r.round_id === id)) return;
    selectedRound = id;
    render(id);
    highlight(id);
    detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  // The ledger re-renders when the agent filter changes.
  const ledger = document.getElementById("ledger");
  if (ledger) {
    new MutationObserver(() => {
      applyChallengeFilter();
      highlight(selectedRound);
    }).observe(ledger, { childList: true, subtree: true });
  }
  // ------------------------------------------------------------- helpers
  const DATA = (() => {
    try { return JSON.parse(document.getElementById("arena-data").textContent); }
    catch (e) { return {}; }
  })();
  const fmtK = n => {
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return String(n);
  };
  const fmtSigned = n => (n > 0 ? "+" : n < 0 ? "\u2212" : "") + fmtK(Math.abs(n));
  const usd = x => {
    if (x == null) return "\u2014";
    const a = Math.abs(x);
    if (a === 0) return "$0";
    if (a < 0.01) return "$" + a.toFixed(4);
    if (a < 1) return "$" + a.toFixed(3);
    return "$" + a.toFixed(2);
  };
  const usdSigned = x => (x > 0 ? "+" : x < 0 ? "\u2212" : "") + usd(Math.abs(x));
  const pct = x => (x == null ? "\u2014" : (x * 100).toFixed(0) + "%");
  const delta = n => (n > 0 ? "+" : "") + n.toFixed(1);
  const TIERS = [
    [1550, "Challenger", "challenger"], [1500, "Grandmaster", "grandmaster"],
    [1450, "Master", "master"], [1400, "Diamond", "diamond"],
    [1350, "Platinum", "platinum"], [1300, "Gold", "gold"],
    [1250, "Silver", "silver"], [-Infinity, "Bronze", "bronze"]
  ];
  const tierOf = rating => TIERS.find(([min]) => rating >= min);

  // =====================================================================
  // Match schematic, draft, roster and champion account.
  // Everything below reads only from the arena-data payload; nothing here
  // needs the network or a build step.
  // =====================================================================

  const ROSTER = DATA.roster || [];
  const CHAMPS = DATA.champions || [];
  const BATTLES = DATA.battles || {};
  const champOf = a =>
    ROSTER.find(c => c.agent === a) ||
    { agent: a, name: a, glyph: a.slice(0, 2).toUpperCase(), accent: "#C8AA6E", title: "", house: "", model: "" };
  const statsOf = a => CHAMPS.find(c => c.agent === a) || null;
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };
  const secs = s => (s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`);

  // ------------------------------------------------------------ sequencer
  const timers = [];
  const clearTimers = () => { timers.forEach(clearTimeout); timers.length = 0; };
  const at = (ms, fn) => { timers.push(setTimeout(fn, ms)); };

  const countTo = (node, target, dur, fmt) => {
    const f = fmt || (v => fmtK(Math.round(v)));
    const t0 = performance.now();
    const tick = now => {
      const p = Math.min(1, (now - t0) / dur);
      node.textContent = f(target * (0.15 + 0.85 * p));
      if (p < 1) requestAnimationFrame(tick);
    };
    node.textContent = f(0);
    requestAnimationFrame(tick);
  };

  // ------------------------------------------------------------ schematic
  const chip = (label, value, state) =>
    `<span class="ia-chip${state ? " " + state : ""}"><i>${state === "bad" ? "\u2717" : state === "skip" ? "\u2013" : "\u2713"}</i>${label}${value ? `<b>${value}</b>` : ""}</span>`;

  function schematicHtml(r) {
    const b = BATTLES[r.round_id] || {};
    const att = b.att || {}, def = b.def || {}, stages = b.stages || {};
    const lane = (side, list) => {
      const chips = (list || []).map(s => chip(s[0], s[1], s[2])).join('<span class="ia-arrow"></span>');
      const meta = side === "att" ? att : def;
      return `<div class="ia-lane ia-lane-${side}">
        <div class="ia-lane-label">
          <span>${side === "att" ? "Attacker" : side === "def" ? "Defender" : "Arbiter"}</span>
          <b>${side === "arb" ? "grader" : (side === "att" ? r.attacker : r.defender)}</b>
          ${side === "arb" ? "" : `<em data-burn="${side}">${usd(meta.cost || 0)}</em>`}
        </div>
        <div class="ia-track">${chips}</div>
      </div>`;
    };

    const mode = !r.theta ? "idle" : r.outcome === "TP" ? "block" : r.outcome === "FN" ? "pass" : "idle";
    const note = !r.theta ? "clean service \u2014 no proof-of-concept"
      : r.outcome === "TP" ? "the proof-of-concept stops at the patch"
      : r.outcome === "FN" ? "the proof-of-concept reaches the canary"
      : "not scored";

    const acts = side => {
      const list = (side === "att" ? att.acts : def.acts) || [];
      const more = (side === "att" ? att.more : def.more) || 0;
      return list.map(a =>
        `<span class="ia-act ${side}" title="${a[0]} ${a[1]}"><i>${a[0]}</i>${a[1] ? `<u>${a[1]}</u>` : ""}${a[2] ? `<u>${usd(a[2])}</u>` : ""}</span>`
      ).join("") + (more ? `<span class="ia-act more">+${more} steps</span>` : "");
    };

    return `<div class="ia-battle" data-mode="${mode}">
      <div class="ia-battle-head">
        <div>
          <div class="ia-battle-title">Match schematic</div>
          <div class="ia-battle-sub">What each side actually did, replayed from the round transcript.</div>
        </div>
        <div class="ia-battle-controls">
          <button class="ia-btn" data-battle="replay">Replay</button>
          <button class="ia-btn" data-battle="all">Reveal all</button>
        </div>
      </div>
      ${lane("att", stages.att)}
      <div class="ia-contest ${mode}">
        <div class="ia-contest-line"></div>
        <span class="ia-contest-note">${note}</span>
        <span class="ia-shield">\u26e8</span>
        <span class="ia-poc-dot"></span>
        <span class="ia-canary">canary</span>
      </div>
      ${lane("def", stages.def)}
      ${lane("arb", stages.arb)}
      <div class="ia-burn">
        <div class="ia-burn-row"><span>att</span><div class="ia-burn-bar"><i data-bar="att"></i></div><b data-burnv="att">0</b></div>
        <div class="ia-burn-row def"><span>def</span><div class="ia-burn-bar"><i data-bar="def"></i></div><b data-burnv="def">0</b></div>
      </div>
      <div class="ia-feed">
        <div class="ia-feed-head"><span>Transcript</span><em>${att.model || r.attacker} \u00b7 ${att.steps || 0} steps \u00b7 ${secs(att.secs || 0)}</em></div>
        <div class="ia-feed-line">${acts("att")}</div>
        <div class="ia-feed-head" style="margin-top:10px"><span>Transcript</span><em>${def.model || r.defender} \u00b7 ${def.steps || 0} steps \u00b7 ${secs(def.secs || 0)}</em></div>
        <div class="ia-feed-line">${acts("def")}</div>
      </div>
    </div>`;
  }

  function playBattle(root) {
    if (!root) return;
    clearTimers();
    const chips = [...root.querySelectorAll(".ia-chip")];
    const acts = [...root.querySelectorAll(".ia-act")];
    const contest = root.querySelector(".ia-contest");
    const bars = { att: root.querySelector('[data-bar="att"]'), def: root.querySelector('[data-bar="def"]') };
    const burnv = { att: root.querySelector('[data-burnv="att"]'), def: root.querySelector('[data-burnv="def"]') };
    const b = BATTLES[(root.closest(".ia-dossier") && root.closest(".ia-dossier").dataset.round) || ""] || {};
    const totals = { att: (b.att || {}).cost || 0, def: (b.def || {}).cost || 0 };
    const peak = Math.max(totals.att, totals.def, 1);

    chips.forEach(c => c.classList.remove("on"));
    acts.forEach(a => a.classList.remove("on"));
    if (contest) {
      contest.classList.remove("live", "hit");
      contest.style.removeProperty("--travel");
    }
    Object.values(bars).forEach(x => x && (x.style.width = "0%"));
    Object.values(burnv).forEach(x => x && (x.textContent = "0"));

    const step = 120;
    let t = 100;
    chips.forEach(c => { const d = t; at(d, () => c.classList.add("on")); t += step; });
    const contestAt = t + 120;
    at(contestAt, () => {
      if (!contest) return;
      contest.classList.add("live");
      contest.style.setProperty("--travel", contest.dataset.mode === "pass" ? "84%" : "52%");
    });
    at(contestAt + 1200, () => contest && contest.classList.add("hit"));
    at(contestAt + 1500, () => {
      Object.entries(bars).forEach(([k, x]) => x && (x.style.width = (totals[k] / peak) * 100 + "%"));
      Object.entries(burnv).forEach(([k, x]) => x && countTo(x, totals[k], 700, usd));
    });
    let a = 260;
    acts.forEach(x => { const d = a; at(d, () => x.classList.add("on")); a += 50; });
  }

  function revealAll(root) {
    if (!root) return;
    clearTimers();
    root.querySelectorAll(".ia-chip, .ia-act").forEach(x => x.classList.add("on"));
    const contest = root.querySelector(".ia-contest");
    if (contest) {
      contest.classList.add("live", "hit");
      contest.style.setProperty("--travel", contest.dataset.mode === "pass" ? "84%" : "52%");
    }
    const b = BATTLES[(root.closest(".ia-dossier") || {}).dataset?.round || ""] || {};
    const totals = { att: (b.att || {}).cost || 0, def: (b.def || {}).cost || 0 };
    const peak = Math.max(totals.att, totals.def, 1);
    Object.entries(totals).forEach(([k, v]) => {
      const bar = root.querySelector(`[data-bar="${k}"]`);
      const num = root.querySelector(`[data-burnv="${k}"]`);
      if (bar) bar.style.width = (v / peak) * 100 + "%";
      if (num) num.textContent = usd(v);
    });
  }

  const gameDetail = document.getElementById("ia-game-detail");
  if (gameDetail) {
    new MutationObserver(() => {
      const dossier = gameDetail.querySelector(".ia-dossier");
      if (!dossier || dossier.querySelector(".ia-battle")) return;
      const id = dossier.dataset.round;
      if (!id) return;
      const r = LEDGER.find(x => x.round_id === id);
      if (!r) return;
      const holder = el("div", "", schematicHtml(r));
      dossier.appendChild(holder.firstElementChild);
      playBattle(dossier.querySelector(".ia-battle"));
    }).observe(gameDetail, { childList: true, subtree: false });
  }

  document.addEventListener("click", ev => {
    const btn = ev.target.closest("[data-battle]");
    if (!btn) return;
    const root = btn.closest(".ia-battle");
    if (btn.dataset.battle === "replay") playBattle(root);
    else revealAll(root);
  });

  // --------------------------------------------------------------- roster
  const rosterHost = document.getElementById("ia-roster");
  if (rosterHost && ROSTER.length) {
    const rankOf = a => {
      const idx = DATA.rows.filter(x => !x.provisional).sort((x, y) => y.rating - x.rating).findIndex(x => x.agent === a);
      return idx >= 0 ? idx + 1 : null;
    };
    // rank order first, champions without a rating last
    const rows = [...ROSTER].sort((x, y) => {
      const a = statsOf(x.agent), b = statsOf(y.agent);
      if (a && b) return b.rating - a.rating;
      return a ? -1 : b ? 1 : 0;
    }).map(c => {
      const s = statsOf(c.agent);
      const tier = s ? tierOf(s.rating) : null;
      return `<tr class="${s ? "" : "bench"}" data-agent="${c.agent}">
        <td>${s ? (rankOf(c.agent) || "\u2014") : "\u2014"}</td>
        <td><div class="r-name"><span class="r-glyph" style="--accent:${c.accent}">${c.glyph}</span>
          <span><b style="font-family:var(--font-display);color:var(--gold-2)">${c.name}</b>
          <em style="display:block;font-style:normal;font-size:10.5px;color:var(--muted)">${c.house}</em></span></div></td>
        <td>${tier ? `<span class="tier ${tier[2]}">${tier[1]}</span>` : `<span class="dim">unplayed</span>`}</td>
        <td class="num">${s ? s.rating.toFixed(1) : "\u2014"}</td>
        <td class="num dim">${s ? s.rating_att.toFixed(1) : "\u2014"}</td>
        <td class="num dim">${s ? s.rating_def.toFixed(1) : "\u2014"}</td>
        <td class="num">${s ? s.rounds : "\u2014"}</td>
        <td class="num">${s ? `${s.wins}\u2013${s.losses}` : "\u2014"}</td>
        <td class="num">${s ? usd(s.cost_total) : "\u2014"}</td>
        <td class="num ${s && s.net_chips < 0 ? "neg" : s ? "pos" : ""}">${s ? usdSigned(s.net_chips) : "\u2014"}</td>
        <td><button class="r-btn" data-profile="${c.agent}">Profile</button></td>
      </tr>`;
    }).join("");
    rosterHost.innerHTML = `<div class="ia-roster-head">
      <div>
        <div class="ia-vault-title">Roster</div>
        <div class="ia-vault-sub">${ROSTER.length} champions on the season roster \u00b7 ${CHAMPS.length} have played \u00b7 the rest are listed without a rating, not with a guessed one.</div>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Champion</th><th>Tier</th><th>Rating</th><th>Att</th><th>Def</th>
      <th>Rounds</th><th>W\u2013L</th><th>Cost</th><th>Chips</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }

  // ---------------------------------------------------------------- draft
  const draftHost = document.getElementById("ia-draft");
  const draft = { side: "blue", blue: null, red: null };

  function h2h(a, b) {
    if (!a || !b) return null;
    const rows = LEDGER.filter(r => (r.attacker === a && r.defender === b) || (r.attacker === b && r.defender === a));
    if (!rows.length) return { n: 0 };
    let aw = 0, bw = 0, tok = 0, last = null;
    rows.forEach(r => {
      const awin = r.attacker === a
        ? (r.outcome === "FN" || r.outcome === "FP")
        : (r.outcome === "TP" || r.outcome === "TN" || r.outcome === "DISCOVERY");
      if (r.outcome === "VOID") { tok += r.cost.attacker + r.cost.defender; last = r; return; }
      awin ? aw++ : bw++;
      tok += r.cost.attacker + r.cost.defender;
      last = r;
    });
    return { n: rows.length, aw, bw, tok, last };
  }

  function renderDraft() {
    if (!draftHost) return;
    const slot = (side, agent, role) => {
      const c = agent ? champOf(agent) : null;
      const s = agent ? statsOf(agent) : null;
      if (!c) return `<div class="ia-slot ${side}"><span class="ia-slot-role">${role}</span>
        <span class="ia-slot-hint">pick a champion below</span></div>`;
      return `<div class="ia-slot ${side} filled"><span class="ia-slot-role">${role}</span>
        <span class="ia-slot-name">${c.name}</span>
        <span class="ia-slot-meta">${s ? `${s.rating.toFixed(1)} \u00b7 ${s.wins}\u2013${s.losses}` : "unplayed"} \u00b7 ${c.model || c.agent}</span></div>`;
    };

    const cards = ROSTER.map(c => {
      const s = statsOf(c.agent);
      const picked = draft.blue === c.agent ? "picked-blue" : draft.red === c.agent ? "picked-red" : "";
      const attW = s && s.attack_survival != null ? Math.round(s.attack_survival * 46) + 4 : 6;
      const defW = s && s.patch_validity != null ? Math.round(s.patch_validity * 46) + 4 : 6;
      return `<div class="ia-champ ${s ? "" : "bench"} ${picked}" data-pick="${c.agent}" style="--accent:${c.accent}" role="button" tabindex="0">
        <span class="ia-champ-badge">${c.glyph}</span>
        <span class="ia-champ-prof" data-profile="${c.agent}">acct</span>
        <span class="ia-champ-name">${c.name}</span>
        <span class="ia-champ-title">${c.title}</span>
        <span class="ia-champ-stats"><b>${s ? s.rating.toFixed(0) : "\u2014"}</b>
          <em>${s ? tierOf(s.rating)[1] : "unplayed"}</em></span>
        <span class="ia-champ-roles"><i class="att" style="width:${attW}px"></i><i class="def" style="width:${defW}px"></i></span>
        ${picked ? `<span class="ia-champ-ribbon">${picked === "picked-blue" ? "blue" : "red"}</span>` : ""}
      </div>`;
    }).join("");

    const m = h2h(draft.blue, draft.red);
    let vs = `<div class="ia-h2h"><div class="ia-h2h-title">Head to head</div>
      <div class="ia-h2h-empty">Pick both sides to see their record.</div></div>`;
    if (draft.blue && draft.red && m) {
      if (!m.n) {
        vs = `<div class="ia-h2h"><div class="ia-h2h-title">Head to head</div>
          <div class="ia-h2h-empty">These two have never met in this season.</div></div>`;
      } else {
        const bl = champOf(draft.blue).name, rd = champOf(draft.red).name;
        vs = `<div class="ia-h2h"><div class="ia-h2h-title">Head to head \u00b7 ${m.n} meeting${m.n === 1 ? "" : "s"}</div>
          <div class="ia-h2h-grid">
            <div><dt>${bl}</dt><dd>${m.aw} win${m.aw === 1 ? "" : "s"}</dd></div>
            <div><dt>${rd}</dt><dd>${m.bw} win${m.bw === 1 ? "" : "s"}</dd></div>
            <div><dt>spend</dt><dd>${usd(m.tok)}</dd></div>
            <div><dt>last meeting</dt><dd>${m.last ? `${m.last.round_id} \u00b7 ${m.last.outcome}` : "\u2014"}</dd></div>
          </div></div>`;
      }
    }

    draftHost.innerHTML = `<div class="ia-draft-head">
      <div>
        <div class="ia-draft-title">Draft</div>
        <div class="ia-draft-sub">Fifteen champions, two sides. Pick who attacks and who defends; the board shows what that pairing has actually done.</div>
      </div>
      <div class="ia-side-toggle">
        <button data-side="blue" class="${draft.side === "blue" ? "on" : ""}">Blue \u00b7 attacker</button>
        <button data-side="red" class="${draft.side === "red" ? "on" : ""}">Red \u00b7 defender</button>
      </div>
    </div>
    <div class="ia-slots">
      ${slot("blue", draft.blue, "Blue side \u00b7 attacker")}
      <div class="ia-slot-vs">VS</div>
      ${slot("red", draft.red, "Red side \u00b7 defender")}
    </div>
    <div class="ia-grid">${cards}</div>
    ${vs}`;
  }

  document.addEventListener("click", ev => {
    const side = ev.target.closest("[data-side]");
    if (side) { draft.side = side.dataset.side; renderDraft(); return; }
    const prof = ev.target.closest("[data-profile]");
    if (prof) { ev.stopPropagation(); openAccount(prof.dataset.profile); return; }
    const pick = ev.target.closest("[data-pick]");
    if (pick) {
      const a = pick.dataset.pick;
      if (draft.side === "blue") draft.blue = draft.blue === a ? null : a;
      else draft.red = draft.red === a ? null : a;
      renderDraft();
    }
  });

  // -------------------------------------------------------------- account
  const RADAR_AXES = [
    ["survival", "attack survives", s => s.attack_survival],
    ["patch", "patch holds", s => s.patch_validity],
    ["precision", "no false alarms", s => (s.fpr == null ? null : 1 - s.fpr)],
    ["winrate", "win rate", s => (s.wins + s.losses ? s.wins / (s.wins + s.losses) : null)],
    ["calibration", "calibration", s => (s.brier == null ? null : Math.max(0, 1 - s.brier * 2))],
    ["efficiency", "tokens saved", s => {
      const per = s.tokens_per_round;
      if (!per) return null;
      return Math.max(0, Math.min(1, 1 - (per - 15000) / 45000));
    }]
  ];

  function radar(s) {
    const R = 44, cx = 62, cy = 58;
    const pt = (i, v) => {
      const a = (Math.PI * 2 * i) / RADAR_AXES.length - Math.PI / 2;
      return [cx + Math.cos(a) * R * v, cy + Math.sin(a) * R * v];
    };
    const rings = [0.33, 0.66, 1].map(v =>
      `<polygon class="ring" points="${RADAR_AXES.map((_, i) => pt(i, v).join(",")).join(" ")}"/>`).join("");
    const axes = RADAR_AXES.map((_, i) => {
      const [x, y] = pt(i, 1);
      return `<line class="axis" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`;
    }).join("");
    const vals = RADAR_AXES.map(([, , f]) => {
      const v = f(s);
      return v == null ? 0.06 : Math.max(0.06, Math.min(1, v));
    });
    const shape = `<polygon class="shape" points="${vals.map((v, i) => pt(i, v).join(",")).join(" ")}"/>`;
    const dots = vals.map((v, i) => {
      const [x, y] = pt(i, v);
      return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1.6" fill="var(--teal)"/>`;
    }).join("");
    return `<svg class="ia-radar" viewBox="0 0 124 116">${rings}${axes}${shape}${dots}</svg>`;
  }

  const radarLegend = s => `<dl class="ia-radar-legend">${RADAR_AXES.map(([, label, f]) => {
    const v = f(s);
    return `<div><dt>${label}</dt><dd>${v == null ? "\u2014" : Math.round(Math.max(0, Math.min(1, v)) * 100) + "%"}</dd></div>`;
  }).join("")}</dl>`;

  function spark(hist) {
    if (!hist || hist.length < 2) return `<div class="ia-h2h-empty" style="font-size:11px">not enough rounds to draw a curve</div>`;
    const W = 260, H = 64, pad = 6;
    const series = [["gen", "var(--gold)"], ["att", "#E06060"], ["def", "#0AC8B9"]];
    const all = hist.flatMap(h => [h[2], h[3], h[4]]);
    const lo = Math.min(...all) - 6, hi = Math.max(...all) + 6;
    const x = i => pad + (i * (W - pad * 2)) / (hist.length - 1);
    const y = v => H - pad - ((v - lo) / (hi - lo || 1)) * (H - pad * 2);
    const lines = series.map(([k, color], idx) => {
      const pts = hist.map((h, i) => `${x(i).toFixed(1)},${y(h[2 + idx]).toFixed(1)}`).join(" ");
      return `<polyline class="line" stroke="${color}" points="${pts}"/>`;
    }).join("");
    return `<svg class="ia-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <line class="base" x1="${pad}" y1="${y(1500)}" x2="${W - pad}" y2="${y(1500)}"/>${lines}</svg>`;
  }

  function openAccount(agent) {
    const c = champOf(agent);
    const s = statsOf(agent);
    let host = document.getElementById("ia-acct");
    if (!host) {
      host = el("div", "ia-acct");
      host.id = "ia-acct";
      host.hidden = true;
      document.body.appendChild(host);
    }

    const tier = s ? tierOf(s.rating) : null;
    const head = `<div class="ia-acct-head">
      <div class="ia-emblem" style="--accent:${c.accent}">${c.glyph}</div>
      <div class="ia-acct-id">
        <h3>${c.name}</h3>
        <span class="ia-acct-title">${c.title || ""}${c.house ? ` \u00b7 ${c.house}` : ""}</span>
        <span class="ia-acct-model">${c.model || agent}</span>
      </div>
      <div class="ia-acct-rating">
        <b>${s ? s.rating.toFixed(1) : "\u2014"}</b>
        <span>${tier ? tier[1] : "unplayed"}</span>
      </div>
      <button class="ia-acct-close" data-acct-close aria-label="Close">\u2715</button>
    </div>`;

    if (!s) {
      host.innerHTML = `<div class="ia-acct-card">${head}
        <div class="ia-panel-mini" style="margin-top:18px">
          <h4>No rounds yet</h4>
          <div class="ia-h2h-empty">This champion is on the roster but has not played a round in
          ${DATA.season_id || "this season"}, so there is no rating to show. Run a match with
          <code>${c.model || agent}</code> to put a number here.</div>
        </div></div>`;
      host.hidden = false;
      return;
    }

    const kv = [
      ["Rounds", s.rounds], ["W\u2013L", `${s.wins}\u2013${s.losses}`], ["Voids", s.voids],
      ["Spend", usd(s.cost_total)], ["$/round", usd(s.cost_per_round)],
      ["Chips", usdSigned(s.net_chips)], ["Brier", s.brier.toFixed(3)],
      ["Patch", s.patch_validity == null ? "\u2014" : pct(s.patch_validity)],
      ["FPR", s.fpr == null ? "\u2014" : pct(s.fpr)]
    ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");

    const role = `<div class="ia-role-block">
      <div class="att"><h5>as attacker</h5><dl class="ia-kv">
        <div><dt>rounds</dt><dd>${s.att.rounds}</dd></div>
        <div><dt>survived</dt><dd>${s.attack_survival == null ? "\u2014" : pct(s.attack_survival)}</dd></div>
        <div><dt>spend</dt><dd>${usd(s.att.cost)}</dd></div>
        <div><dt>$/round</dt><dd>${s.att.rounds ? usd(s.att.cost / s.att.rounds) : "\u2014"}</dd></div>
      </dl></div>
      <div class="def"><h5>as defender</h5><dl class="ia-kv">
        <div><dt>rounds</dt><dd>${s.def.rounds}</dd></div>
        <div><dt>TP/FN</dt><dd>${s.def.tp}/${s.def.fn}</dd></div>
        <div><dt>FP/TN</dt><dd>${s.def.fp}/${s.def.tn}</dd></div>
        <div><dt>spend</dt><dd>${usd(s.def.cost)}</dd></div>
      </dl></div></div>`;

    const h2hRows = (s.h2h || []).map(([opp, n, w, l]) => {
      const oc = champOf(opp);
      return `<div class="ia-h2hrow"><b>${oc.name}</b><span>${w}\u2013${l}</span><span>${n} played</span></div>`;
    }).join("") || `<div class="ia-h2h-empty">No meetings recorded.</div>`;

    const hist = (s.rounds_list || []).map(([rid, mid, roleName, opp, theta, outcome, tok, d]) => {
      const cls = outcome === "VOID" ? "void" : (roleName === "attacker" ? (outcome === "FN" || outcome === "FP") : (outcome === "TP" || outcome === "TN" || outcome === "DISCOVERY")) ? "win" : "loss";
      return `<tr data-open-round="${rid}">
        <td>${rid}</td><td>${roleName === "attacker" ? "atk" : "def"}</td>
        <td>${champOf(opp).name}</td><td>${theta ? "\u2694\uFE0E" : "\u25cb"}</td>
        <td class="${cls}">${outcome}</td><td>${usd(tok)}</td>
        <td class="${d >= 0 ? "win" : "loss"}">${delta(d)}</td></tr>`;
    }).join("");

    host.innerHTML = `<div class="ia-acct-card">${head}
      <div class="ia-acct-body">
        <div class="ia-acct-col">
          <div class="ia-panel-mini"><h4>Shape</h4>${radar(s)}${radarLegend(s)}</div>
          <div class="ia-panel-mini"><h4>Rating over the season</h4>${spark(s.hist)}
            <div style="display:flex;gap:10px;margin-top:6px;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase">
              <span style="color:var(--gold)">general</span><span style="color:#E06060">attack</span><span style="color:var(--teal)">defence</span>
            </div></div>
          <div class="ia-panel-mini"><h4>Record</h4><dl class="ia-kv">${kv}</dl></div>
        </div>
        <div class="ia-acct-col">
          ${role}
          <div class="ia-panel-mini"><h4>Head to head</h4><div class="ia-h2hlist">${h2hRows}</div></div>
          <div class="ia-panel-mini"><h4>Every round</h4>
            <div style="max-height:220px;overflow:auto">
            <table class="ia-hist"><thead><tr><th>round</th><th>role</th><th>vs</th><th>\u03b8</th><th>outcome</th><th>cost</th><th>\u0394elo</th></tr></thead>
            <tbody>${hist}</tbody></table></div></div>
        </div>
      </div></div>`;
    host.hidden = false;
  }

  document.addEventListener("click", ev => {
    if (ev.target.closest("[data-acct-close]") || (ev.target.id === "ia-acct")) {
      const host = document.getElementById("ia-acct");
      if (host) host.hidden = true;
      return;
    }
    const row = ev.target.closest("[data-open-round]");
    if (row) {
      const host = document.getElementById("ia-acct");
      if (host) host.hidden = true;
      const id = row.dataset.openRound;
      if (LEDGER.some(r => r.round_id === id)) {
        render(id);
        highlight(id);
        detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  });

  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape") {
      const host = document.getElementById("ia-acct");
      if (host) host.hidden = true;
    }
  });

  renderDraft();

})();
