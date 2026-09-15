# rh_progression_chart — Progression Charts plugin for RotorHazard

Live pilot progression charts served directly from your RotorHazard timer.

## What it does

Adds a `/progression` page to your timer's web interface showing:

- **Fastest lap per race** — how each pilot's single-lap pace evolved through the event
- **Best 3 consecutive laps per race** — consistency/pace trends
- **Class buttons** — one per race class (e.g. Qualifiers, Finals); each shows only that class's races
- **Pilot chips** — click a pilot to toggle them on/off the charts and stats
- **Per-class stats cards** — best lap, best 3 consecutives, average lap, race count per pilot
- **Auto-refresh** — the page polls for new/marshalled data every 20s and updates itself; your phase and pilot selections are preserved
- **Works offline** — Chart.js is bundled; no internet needed at the field

## Installation

**Via the plugin manager (once listed in community plugins):** Settings → Plugins → search "Progression Charts" → Install.

**Manual:** copy the `custom_plugins/rh_progression_chart/` directory into your timer's `~/rh-data/plugins/` directory and restart the server.

## Usage

Open `http://<timer-ip>:5000/progression` on any device on the same network (phone, tablet, laptop). Pick a class with the phase buttons, toggle pilots with the chips, and leave the page open — it updates itself as races are saved and marshalled.

## How the numbers are computed

- Laps shorter than 10s are treated as start crossings / false detections and excluded
- Marshal-deleted laps are excluded
- Fastest laps above 50s and consecutive sums above 130s are treated as crash/pit-lap outliers and excluded
- "Best 3 consecutive" is the minimum sum over all sliding windows of 3 consecutive laps in a race

## License

MIT