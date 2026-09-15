"""
Progression Charts Plugin for RotorHazard

Live pilot progression charts: fastest lap + best 3 consecutive laps
per saved race, filtered by class (Qualifiers/Finals), with per-pilot
toggle chips. Serves a self-contained Chart.js page from the timer.

Route: /progression
"""

import logging
from flask import Blueprint, Response

from RHAPI import RHAPI
from eventmanager import Evt

logger = logging.getLogger(__name__)

MIN_LAP_MS = 10000        # laps below this are start crossings / false detections
OUTLIER_FASTEST_S = 50    # fastest lap above this = crash/pit lap -> drop
OUTLIER_CONSEC_S = 130    # consecutives above this = crash/pit lap -> drop

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__EVENT_NAME__ — Progression</title>
<script>__CHARTJS__</script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; padding: 20px; }
  h1 { text-align: center; font-size: 1.5rem; margin-bottom: 4px; color: #58a6ff; }
  .subtitle { text-align: center; color: #8b949e; font-size: 0.85rem; margin-bottom: 16px; }
  .controls { max-width: 1400px; margin: 0 auto 16px; display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  .phase-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .pilot-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .toggle-btn { background: #21262d; border: 1px solid #30363d; color: #8b949e; padding: 5px 14px; border-radius: 8px; cursor: pointer; font-size: 0.82rem; transition: all 0.2s; }
  .toggle-btn:hover { border-color: #58a6ff; color: #58a6ff; }
  .toggle-btn.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }
  .pilot-chip { display: inline-flex; align-items: center; gap: 4px; background: #21262d; border: 1px solid #30363d; padding: 3px 10px; border-radius: 20px; cursor: pointer; font-size: 0.78rem; transition: all 0.15s; user-select: none; }
  .pilot-chip:hover { border-color: #58a6ff; }
  .pilot-chip.off { opacity: 0.4; }
  .pilot-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .label-tag { font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 4px; }
  .chart-container { max-width: 1400px; margin: 0 auto 28px; background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
  .chart-title { font-size: 1.1rem; margin-bottom: 8px; }
  canvas { max-height: 380px; }
  .stats-grid { max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
  .pilot-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px; text-align: center; }
  .pilot-card .name { font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; }
  .pilot-card .stat { font-size: 0.72rem; color: #8b949e; margin-top: 2px; }
  .pilot-card .value { font-size: 1.05rem; font-weight: 700; color: #58a6ff; }
  .pilot-card .value.consec { color: #3fb950; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
  .empty { text-align: center; color: #8b949e; padding: 40px; }
</style>
</head>
<body>
  <h1>🏁 __EVENT_NAME__ — Progression</h1>
  <p class="subtitle">Live from timer · Marshalled data</p>
  <div id="content" class="empty">Loading…</div>
<script>
const DATA = __DATA_JSON__;

const PALETTE = ['#FF6B6B','#4ECDC4','#FFD93D','#6BCB77','#4D96FF','#FF9F43','#A55EEA','#26C6DA','#F06292','#BA68C8','#4DB6AC','#FFB74D'];
const pilotColors = {};
DATA.pilots.forEach((p, i) => { pilotColors[p] = PALETTE[i % PALETTE.length]; });

// Build phases from DATA — one button per class, no "All Races"
const phases = {};
const classNames = [...new Set(DATA.races.map(r => r.class_name))];
classNames.forEach(c => { phases[c] = { label: c, classFilter: c }; });

function shortenHeat(name) {
  if (!name) return '';
  if (name.includes('Group A')) return 'Grp A';
  if (name.includes('Group B')) return 'Grp B';
  return name;
}

// Compute per-phase datasets
Object.keys(phases).forEach(pk => {
  const ph = phases[pk];
  const races = DATA.races.filter(r => !ph.classFilter || r.class_name === ph.classFilter);
  const labels = races.map(r => `${r.class_name} R${r.round} · ${shortenHeat(r.heat_name)}`);

  const pilotsInPhase = [...new Set(races.flatMap(r => Object.keys(r.results)))];
  const fastest = [], consec = [];
  pilotsInPhase.forEach(p => {
    fastest.push({
      label: p,
      data: races.map(r => r.results[p] ? r.results[p].fastest : null),
      borderColor: pilotColors[p], backgroundColor: pilotColors[p] + '20',
      tension: 0.3, spanGaps: true, pointRadius: 3, pointHoverRadius: 6
    });
    consec.push({
      label: p,
      data: races.map(r => r.results[p] ? r.results[p].consec : null),
      borderColor: pilotColors[p], backgroundColor: pilotColors[p] + '20',
      tension: 0.3, spanGaps: true, pointRadius: 3, pointHoverRadius: 6
    });
  });

  // Stats
  const stats = {};
  pilotsInPhase.forEach(p => {
    const fv = races.map(r => r.results[p] ? r.results[p].fastest : null).filter(v => v !== null);
    const cv = races.map(r => r.results[p] ? r.results[p].consec : null).filter(v => v !== null);
    stats[p] = {
      best_fastest: fv.length ? Math.min(...fv) : null,
      avg_fastest: fv.length ? fv.reduce((a,b) => a+b, 0) / fv.length : null,
      best_consec: cv.length ? Math.min(...cv) : null,
      races: fv.length,
      color: pilotColors[p]
    };
  });

  ph.labels = labels;
  ph.fastest = fastest;
  ph.consec = consec;
  ph.stats = stats;
  ph.pilots = pilotsInPhase;
});

let visiblePilots = new Set(DATA.pilots);
let currentPhase = classNames[0];  // first class is the default
let fc, cc;
let chartJsReady = typeof Chart !== 'undefined';

// Build controls
const content = document.getElementById('content');
content.className = '';
content.innerHTML = `
  <div class="controls">
    <div class="phase-row" id="phaseRow"><span class="label-tag">Phase</span></div>
    <div class="pilot-row" id="pilotRow"><span class="label-tag">Pilots</span></div>
  </div>
  <div class="chart-container">
    <div class="chart-title">⚡ Fastest Lap per Race (seconds — lower is better)</div>
    <canvas id="fastestChart"></canvas>
  </div>
  <div class="chart-container">
    <div class="chart-title">🔥 Best 3 Consecutive Laps per Race (seconds — lower is better)</div>
    <canvas id="consecChart"></canvas>
  </div>
  <div class="stats-grid" id="statsGrid"></div>
  <p style="text-align:center;color:#8b949e;font-size:0.75rem;margin-top:12px">Auto-refreshes on reload · Data: marshalled saved races</p>
`;

const phaseRow = document.getElementById('phaseRow');
Object.keys(phases).forEach(pk => {
  const btn = document.createElement('button');
  btn.className = 'toggle-btn' + (pk === currentPhase ? ' active' : '');
  btn.textContent = phases[pk].label;
  btn.dataset.phase = pk;
  btn.addEventListener('click', () => {
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPhase = pk;
    rebuildPilotChips();
    renderPhase();
  });
  phaseRow.appendChild(btn);
});

const pilotRow = document.getElementById('pilotRow');
function rebuildPilotChips() {
  pilotRow.innerHTML = '<span class="label-tag">Pilots</span>';
  phases[currentPhase].pilots.forEach(p => {
    const chip = document.createElement('span');
    chip.className = 'pilot-chip' + (visiblePilots.has(p) ? '' : ' off');
    chip.innerHTML = `<span class="pilot-dot" style="background:${pilotColors[p]}"></span>${p}`;
    chip.addEventListener('click', () => {
      if (visiblePilots.has(p)) { visiblePilots.delete(p); chip.classList.add('off'); }
      else { visiblePilots.add(p); chip.classList.remove('off'); }
      saveSelections();
      renderPhase();
    });
    pilotRow.appendChild(chip);
  });
}

function makeOptions() {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'nearest', intersect: false, axis: 'x' },
    plugins: {
      legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 10 }, usePointStyle: true, padding: 10, boxWidth: 8 } },
      tooltip: { backgroundColor: '#161b22', borderColor: '#30363d', borderWidth: 1, titleColor: '#e6edf3', bodyColor: '#e6edf3', padding: 10,
        callbacks: { title: ctx => ctx[0].label, label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(2) + 's' } }
    },
    scales: {
      x: { ticks: { color: '#8b949e', font: { size: 7 }, maxRotation: 60, autoSkip: false }, grid: { color: '#21262d' } },
      y: { ticks: { color: '#8b949e', callback: v => v + 's' }, grid: { color: '#21262d' }, title: { display: true, text: 'Seconds', color: '#8b949e' } }
    }
  };
}

function renderPhase() {
  const ph = phases[currentPhase];
  const fd = ph.fastest.filter(ds => visiblePilots.has(ds.label));
  const cd = ph.consec.filter(ds => visiblePilots.has(ds.label));
  if (fc) fc.destroy();
  if (cc) cc.destroy();
  fc = new Chart(document.getElementById('fastestChart'), { type: 'line', data: { labels: ph.labels, datasets: fd }, options: makeOptions() });
  cc = new Chart(document.getElementById('consecChart'), { type: 'line', data: { labels: ph.labels, datasets: cd }, options: makeOptions() });
  const visible = ph.pilots.filter(p => visiblePilots.has(p));
  document.getElementById('statsGrid').innerHTML = visible.map(p => {
    const s = ph.stats[p];
    return `<div class="pilot-card"><div class="name"><span class="swatch" style="background:${s.color}"></span>${p}</div>
      <div class="stat">Best Lap</div><div class="value">${s.best_fastest != null ? s.best_fastest.toFixed(2)+'s' : '—'}</div>
      <div class="stat">Best 3 Consec</div><div class="value consec">${s.best_consec != null ? s.best_consec.toFixed(2)+'s' : '—'}</div>
      <div class="stat">Avg Lap</div><div class="stat" style="font-size:0.8rem;color:#8b949e">${s.avg_fastest != null ? s.avg_fastest.toFixed(2)+'s' : '—'}</div>
      <div class="stat">Races: ${s.races}</div></div>`;
  }).join('');
}

rebuildPilotChips();
if (chartJsReady) {
  renderPhase();
} else {
  document.getElementById('statsGrid').innerHTML = '<div class="empty">Chart library failed to load</div>';
}

// --- Selection persistence + change-detection auto-refresh ---

// Save/restore phase + pilot selections (survive reloads)
let restoring = false;
function saveSelections() {
  try {
    localStorage.setItem('rh_progression_sel', JSON.stringify({
      phase: currentPhase,
      pilots: [...visiblePilots]
    }));
  } catch (e) {}
}
function restoreSelections() {
  try {
    const sel = JSON.parse(localStorage.getItem('rh_progression_sel'));
    if (!sel) return;
    if (phases[sel.phase]) {
      currentPhase = sel.phase;
      document.querySelectorAll('.toggle-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.phase === sel.phase));
    }
    // Keep only pilots that exist in current data
    visiblePilots = new Set((sel.pilots || []).filter(p => DATA.pilots.includes(p)));
    if (visiblePilots.size === 0) visiblePilots = new Set(DATA.pilots);
  } catch (e) {}
}
restoreSelections();
rebuildPilotChips();
if (chartJsReady) renderPhase();
document.querySelectorAll('.toggle-btn').forEach(b =>
  b.addEventListener('click', saveSelections));

// Poll /progression/data every 20s; reload page only when race data changed
let currentDataVer = JSON.stringify(DATA.races.length) + ':' +
  DATA.races.map(r => r.race_id + ':' + Object.keys(r.results).sort().join(',')).join('|');

setInterval(async () => {
  try {
    const resp = await fetch('/progression/data', { cache: 'no-store' });
    if (!resp.ok) return;
    const fresh = await resp.json();
    if (fresh.error || !fresh.races) return;
    const ver = JSON.stringify(fresh.races.length) + ':' +
      fresh.races.map(r => r.race_id + ':' + Object.keys(r.results).sort().join(',')).join('|');
    if (ver !== currentDataVer) {
      saveSelections();
      location.reload();
    }
  } catch (e) { /* timer unreachable — try again next cycle */ }
}, 20000);
</script>
</body>
</html>"""

CHARTJS_CACHE = {"data": None}


def _load_chartjs():
    """Load Chart.js from the plugin's static dir (cached in memory)."""
    if CHARTJS_CACHE["data"] is None:
        import os
        path = os.path.join(os.path.dirname(__file__), "static", "chart.umd.min.js")
        try:
            with open(path) as f:
                CHARTJS_CACHE["data"] = f.read()
        except OSError:
            logger.warning("rh_progression_chart: chart.umd.min.js missing from static dir")
            CHARTJS_CACHE["data"] = ""
    return CHARTJS_CACHE["data"]


def _collect_data(rhapi: RHAPI) -> dict:
    """Walk saved races -> pilotruns -> laps and compute per-race stats."""
    pilots = {p.id: p.display_callsign for p in rhapi.db.pilots}
    heats = {h.id: h for h in rhapi.db.heats}
    classes = {c.id: c for c in rhapi.db.raceclasses}

    race_rows = []
    for race in rhapi.db.races:
        heat = heats.get(race.heat_id)
        cls = classes.get(race.class_id)
        if heat is None or cls is None:
            continue
        race_rows.append({
            "race_id": race.id,
            "round_id": race.round_id,
            "heat_id": race.heat_id,
            "class_id": race.class_id,
            "heat_name": getattr(heat, "name", None) or getattr(heat, "note", "") or f"Heat {race.heat_id}",
            "class_name": cls.name,
            "results": {},
        })

    race_by_id = {r["race_id"]: r for r in race_rows}

    for run in rhapi.db.pilotruns:
        row = race_by_id.get(run.race_id)
        if row is None:
            continue
        pid = run.pilot_id
        if not pid or pid not in pilots:
            continue

        laps = [
            l.lap_time for l in rhapi.db.laps_by_pilotrun(run.id)
            if not getattr(l, "deleted", 0) and l.lap_time and l.lap_time >= MIN_LAP_MS
        ]
        if not laps:
            continue

        fastest = min(laps) / 1000.0
        consec = None
        if len(laps) >= 3:
            consec = min(sum(laps[i:i + 3]) for i in range(len(laps) - 2)) / 1000.0

        if fastest > OUTLIER_FASTEST_S:
            fastest = None
        if consec is not None and consec > OUTLIER_CONSEC_S:
            consec = None
        if fastest is None and consec is None:
            continue

        row["results"][pilots[pid]] = {"fastest": fastest, "consec": consec, "laps": len(laps)}

    # Drop races with no usable results, sort by class order then round
    race_rows = [r for r in race_rows if r["results"]]
    class_order = {c.id: i for i, c in enumerate(
        sorted(classes.values(), key=lambda c: (c.id != 1, c.id)))}
    race_rows.sort(key=lambda r: (r["class_id"], r["round_id"], r["race_id"]))

    used_pilots = sorted({p for r in race_rows for p in r["results"]})

    event_name = rhapi.db.option("eventName", "") or "Event"

    return {
        "event_name": event_name,
        "pilots": used_pilots,
        "races": [
            {
                "race_id": r["race_id"],
                "class_name": r["class_name"],
                "heat_name": r["heat_name"],
                "round": r["round_id"],
                "results": r["results"],
            }
            for r in race_rows
        ],
    }


def initialize(rhapi: RHAPI) -> None:
    """Register blueprint + settings link."""
    logger.info("Progression Charts plugin initialising")

    bp = Blueprint(
        "rh_progression_chart",
        __name__,
        static_folder="static",
        static_url_path="/rh_progression_chart/static",
    )

    @bp.route("/progression")
    def progression_page():
        try:
            data = _collect_data(rhapi)
        except Exception:
            logger.exception("Progression Charts: data collection failed")
            return Response("<h1>Progression Charts</h1><p>Error collecting race data — check timer log.</p>", mimetype="text/html")

        if not data["races"]:
            return Response("<h1>Progression Charts</h1><p>No saved races yet.</p>", mimetype="text/html")

        chartjs = _load_chartjs()
        page = PAGE_TEMPLATE
        page = page.replace("__EVENT_NAME__", data["event_name"])
        page = page.replace("__CHARTJS__", chartjs)
        page = page.replace("__DATA_JSON__", _safe_json(data))
        return Response(page, mimetype="text/html")

    @bp.route("/progression/data")
    def progression_data():
        """Lightweight JSON endpoint for the page's change-detection poll."""
        try:
            data = _collect_data(rhapi)
            return Response(_safe_json(data), mimetype="application/json")
        except Exception:
            logger.exception("Progression Charts: data endpoint failed")
            return Response('{"error": "collection failed"}', status=500, mimetype="application/json")

    rhapi.ui.blueprint_add(bp)

    rhapi.ui.register_panel("progression_settings", "Progression Charts", "settings")
    rhapi.ui.register_markdown(
        "progression_settings",
        "Progression Charts",
        "Live pilot progression chart available [here](/progression)"
    )

    logger.info("Progression Charts plugin ready — page at /progression")


def _safe_json(obj) -> str:
    import json as _json
    return _json.dumps(obj, separators=(",", ":"))


def init_plugin(args: dict) -> None:
    pass