import csv
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

import serial
import serial.tools.list_ports
from flask import Flask, jsonify, render_template_string

CSV_DATEI = "messdaten.csv"
INTERVALL = 300    # Sekunden zwischen zwei Diagrammpunkten (5 min)
MAX_PUNKTE = 2016  # 7 Tage bei 5 min Abstand

latest = {"temp": None, "hum": None, "ts": None}
history = deque(maxlen=MAX_PUNKTE)
letzter_eintrag = 0


def finde_port():
    for p in serial.tools.list_ports.comports():
        if p.vid == 0x303A:  # Espressif (ESP32-C3)
            return p.device
    return None


def log_csv(ts, temp, hum):
    with open(CSV_DATEI, "a", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=";").writerow(
            [datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), temp, hum]
        )


def lade_verlauf():
    """Liest die CSV beim Start ein, damit die Diagramme nicht leer beginnen."""
    global letzter_eintrag
    try:
        with open(CSV_DATEI, newline="", encoding="utf-8") as f:
            for row in csv.reader(f, delimiter=";"):
                try:
                    ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").timestamp()
                    history.append({"ts": ts, "temp": float(row[1]), "hum": float(row[2])})
                except (ValueError, IndexError):
                    continue  # kaputte Zeile überspringen
    except FileNotFoundError:
        pass
    if history:
        letzter_eintrag = history[-1]["ts"]


def reader():
    global letzter_eintrag
    while True:
        port = finde_port()
        if port is None:
            time.sleep(2)
            continue
        try:
            with serial.Serial(port, 115200, timeout=2) as s:
                while True:
                    line = s.readline().decode(errors="ignore").strip()
                    m = re.match(r"T=([\d.\-]+) H=([\d.]+)", line)
                    if m:
                        ts = time.time()
                        temp, hum = float(m[1]), float(m[2])
                        latest.update(temp=temp, hum=hum, ts=ts)
                        if ts - letzter_eintrag >= INTERVALL:
                            history.append({"ts": ts, "temp": temp, "hum": hum})
                            log_csv(ts, temp, hum)
                            letzter_eintrag = ts
        except serial.SerialException:
            time.sleep(2)


app = Flask(__name__)

PAGE = """
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZAÜ-Temperatur und Feuchtigkeitslevel</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; background: #111; color: #eee; font-family: system-ui; }

  /* Seite füllt genau die Fensterhöhe; erst unter 560 px Höhe wird gescrollt */
  .page {
    height: 100vh; height: 100dvh; min-height: 560px;
    display: flex; flex-direction: column;
    padding: 0.8rem 2rem 1rem;
  }
  h1 { text-align: center; font-weight: 600; font-size: 1.6rem; margin: 0 0 0.7rem; }

  .cards { display: flex; gap: 1.5rem; justify-content: center; flex-shrink: 0; }
  .card { background: #1e1e1e; padding: 0.6rem 2.5rem; border-radius: 12px; text-align: center; }
  .val { font-size: 2.2rem; font-weight: 600; line-height: 1.15; }
  .lbl { color: #888; font-size: 0.85rem; }

  /* Diagramm-Bereich nimmt den gesamten Rest der Höhe */
  .grid {
    flex: 1; min-height: 0; margin-top: 0.6rem;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr) auto minmax(0, 1fr);
    gap: 0.4rem 1.5rem;
    max-width: 1300px; width: 100%; margin-left: auto; margin-right: auto;
  }
  h2 {
    grid-column: 1 / -1; text-align: center; font-weight: 500;
    font-size: 0.95rem; color: #aaa; margin: 0.3rem 0 0;
  }
  .chartbox { position: relative; min-height: 0; overflow: hidden;
              background: #1e1e1e; border-radius: 12px; }
  .cv { position: absolute; inset: 0.5rem; }
</style>

<div class="page">
  <h1>ZAÜ-Temperatur und Feuchtigkeitslevel</h1>

  <div class="cards">
    <div class="card"><div class="lbl">Temperatur</div><div class="val"><span id="t">–</span> °C</div></div>
    <div class="card"><div class="lbl">Luftfeuchte</div><div class="val"><span id="h">–</span> %</div></div>
  </div>

  <div class="grid">
    <h2>Letzte Stunde (alle 5 Minuten ein Wert, max. 12 Werte)</h2>
    <div class="chartbox"><div class="cv"><canvas id="chartT1"></canvas></div></div>
    <div class="chartbox"><div class="cv"><canvas id="chartH1"></canvas></div></div>

    <h2>Letzte 24 Stunden (Stundenmittelwerte)</h2>
    <div class="chartbox"><div class="cv"><canvas id="chartT24"></canvas></div></div>
    <div class="chartbox"><div class="cv"><canvas id="chartH24"></canvas></div></div>
  </div>
</div>

<script>
// minSpan = kleinste Spanne der y-Achse (Temperatur in °C, Luftfeuchte in %)
const MIN_SPAN_T = 0.5;
const MIN_SPAN_H = 4;

function makeChart(canvasId, label, color) {
  return new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: { labels: [], datasets: [{ label: label, data: [], borderColor: color,
            backgroundColor: color, pointRadius: 3, borderWidth: 2, tension: 0.3 }] },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#888', maxTicksLimit: 8 }, grid: { color: '#2a2a2a' } },
        y: { ticks: { color: '#888', precision: 0 }, grid: { color: '#2a2a2a' } }
      },
      plugins: { legend: { labels: { color: '#ccc', boxWidth: 30, boxHeight: 10 } } }
    }
  });
}

const chartT1  = makeChart('chartT1',  'Temperatur (°C) – letzte Stunde', '#ff7043');
const chartH1  = makeChart('chartH1',  'Luftfeuchte (%) – letzte Stunde', '#42a5f5');
const chartT24 = makeChart('chartT24', 'Temperatur (°C) – letzte 24 h', '#ff7043');
const chartH24 = makeChart('chartH24', 'Luftfeuchte (%) – letzte 24 h', '#42a5f5');

const fmtZeit = { hour: '2-digit', minute: '2-digit' };
const fmtStunde = { weekday: 'short', hour: '2-digit', minute: '2-digit' };

// y-Achse: mindestens minSpan breit, zentriert um die Daten, auf ganze Zahlen gerundet
function setzeAchse(chart, werte, minSpan) {
  if (!werte.length) return;
  const lo = Math.min(...werte), hi = Math.max(...werte);
  const mitte = (lo + hi) / 2;
  const span = Math.max((hi - lo) * 1.2, minSpan);
  chart.options.scales.y.min = Math.floor(mitte - span / 2);
  chart.options.scales.y.max = Math.ceil(mitte + span / 2);
}

function fuelle(chartT, chartH, punkte, fmt) {
  const labels = punkte.map(p => new Date(p.ts * 1000).toLocaleString('de-DE', fmt));
  const temps = punkte.map(p => p.temp);
  const hums = punkte.map(p => p.hum);

  chartT.data.labels = labels;
  chartT.data.datasets[0].data = temps;
  setzeAchse(chartT, temps, MIN_SPAN_T);
  chartT.update();

  chartH.data.labels = labels;
  chartH.data.datasets[0].data = hums;
  setzeAchse(chartH, hums, MIN_SPAN_H);
  chartH.update();
}

async function updateKacheln() {
  try {
    const d = await (await fetch('/api/data')).json();
    if (d.temp !== null) {
      document.getElementById('t').textContent = d.temp.toFixed(1);
      document.getElementById('h').textContent = d.hum.toFixed(1);
    }
  } catch (e) { /* Server kurz nicht erreichbar */ }
}

async function updateCharts() {
  try {
    const h1 = await (await fetch('/api/history/1h')).json();
    fuelle(chartT1, chartH1, h1, fmtZeit);
    const h24 = await (await fetch('/api/history/24h')).json();
    fuelle(chartT24, chartH24, h24, fmtStunde);
  } catch (e) { /* Server kurz nicht erreichbar */ }
}

updateKacheln();
updateCharts();
setInterval(updateKacheln, 5000);
setInterval(updateCharts, 60000);
</script>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/data")
def data():
    return jsonify(latest)


@app.route("/api/history/1h")
def hist_1h():
    grenze = time.time() - 3600
    punkte = [p for p in history if p["ts"] >= grenze]
    return jsonify(punkte[-12:])


@app.route("/api/history/24h")
def hist_24h():
    grenze = time.time() - 24 * 3600
    gruppen = defaultdict(list)
    for p in history:
        if p["ts"] >= grenze:
            stunde = datetime.fromtimestamp(p["ts"]).replace(minute=0, second=0, microsecond=0)
            gruppen[stunde].append(p)
    ergebnis = []
    for stunde in sorted(gruppen):
        pts = gruppen[stunde]
        ergebnis.append({
            "ts": stunde.timestamp(),
            "temp": round(sum(p["temp"] for p in pts) / len(pts), 1),
            "hum": round(sum(p["hum"] for p in pts) / len(pts), 1),
        })
    return jsonify(ergebnis)


if __name__ == "__main__":
    lade_verlauf()
    threading.Thread(target=reader, daemon=True).start()
    app.run(host="127.0.0.1", port=5000)