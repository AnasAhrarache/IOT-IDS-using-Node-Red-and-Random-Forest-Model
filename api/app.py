from flask import Flask, request, jsonify, Response, render_template_string
import joblib
import json
import numpy as np
import pandas as pd
import os
import time
import threading
from collections import deque
from datetime import datetime

# ─────────────────────────────────────────
# Load model
# ─────────────────────────────────────────
MODEL_PATH = "D:/IOT IDS/model/"

rf_model = joblib.load(MODEL_PATH + "random_forest.pkl")
le       = joblib.load(MODEL_PATH + "label_encoder.pkl")

with open(MODEL_PATH + "features.json", "r") as f:
    FEATURE_COLS = json.load(f)

print(f"Model loaded. Classes: {list(le.classes_)}")

# ─────────────────────────────────────────
# In-memory storage
# ─────────────────────────────────────────
detections      = deque(maxlen=100)   # last 100 detections
sse_clients     = []                  # connected dashboard clients
stats = {
    "total"    : 0,
    "attacks"  : 0,
    "normal"   : 0,
    "flood"    : 0,
    "spoof"    : 0,
    "anomaly"  : 0,
    "devices"  : set()
}

# ─────────────────────────────────────────
# SSE broadcaster
# ─────────────────────────────────────────
def broadcast(data):
    """Send event to all connected dashboard clients."""
    dead = []
    for q in sse_clients:
        try:
            q.append(data)
        except:
            dead.append(q)
    for q in dead:
        sse_clients.remove(q)

# ─────────────────────────────────────────
# Flask App
# ─────────────────────────────────────────
app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        missing = [f for f in FEATURE_COLS if f not in data]
        if missing:
            return jsonify({"error": f"Missing: {missing}"}), 400

        # Predict
        features           = pd.DataFrame([[data[f] for f in FEATURE_COLS]], 
                                           columns=FEATURE_COLS)
        prediction_encoded = rf_model.predict(features)[0]
        prediction_label   = le.inverse_transform([prediction_encoded])[0]
        probabilities      = rf_model.predict_proba(features)[0]
        confidence         = float(probabilities.max())
        is_attack          = prediction_label != "normal"

        # Build detection record
        detection = {
            "timestamp"  : datetime.now().strftime("%H:%M:%S"),
            "device_id"  : data.get("device_id", "unknown"),
            "prediction" : prediction_label,
            "confidence" : round(confidence, 4),
            "is_attack"  : is_attack,
            "mean_temp"  : data.get("mean_temp", 0),
            "mean_interval": data.get("mean_interval", 0)
        }

        # Update stats
        stats["total"]  += 1
        stats["devices"].add(detection["device_id"])
        if is_attack:
            stats["attacks"] += 1
            stats[prediction_label] = stats.get(prediction_label, 0) + 1
        else:
            stats["normal"] += 1

        # Store detection
        detections.appendleft(detection)

        # Broadcast to dashboard
        broadcast(json.dumps({
            "type"     : "detection",
            "detection": detection,
            "stats"    : {
                "total"  : stats["total"],
                "attacks": stats["attacks"],
                "normal" : stats["normal"],
                "flood"  : stats.get("flood", 0),
                "spoof"  : stats.get("spoof", 0),
                "anomaly": stats.get("anomaly", 0),
                "devices": len(stats["devices"])
            }
        }))

        print(f"[PREDICT] {prediction_label} "
              f"(confidence={confidence:.4f}, "
              f"device={detection['device_id']})")

        return jsonify({
            "prediction": prediction_label,
            "confidence": round(confidence, 4),
            "is_attack" : is_attack,
            "status"    : "ok"
        })

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/events")
def events():
    """SSE endpoint — dashboard connects here for live updates."""
    client_queue = deque(maxlen=50)
    sse_clients.append(client_queue)

    def stream():
        # Send current stats immediately on connect
        yield f"data: {json.dumps({'type': 'init', 'detections': list(detections), 'stats': {'total': stats['total'], 'attacks': stats['attacks'], 'normal': stats['normal'], 'flood': stats.get('flood', 0), 'spoof': stats.get('spoof', 0), 'anomaly': stats.get('anomaly', 0), 'devices': len(stats['devices'])}})}\n\n"

        while True:
            if client_queue:
                data = client_queue.popleft()
                yield f"data: {data}\n\n"
            else:
                yield ": heartbeat\n\n"
                time.sleep(1)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control"              : "no-cache",
            "X-Accel-Buffering"          : "no",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

# ─────────────────────────────────────────
# Dashboard HTML
# ─────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IoT IDS — Live Security Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: #0a0e1a;
    color: #e0e6f0;
    font-family: 'Segoe UI', monospace;
    min-height: 100vh;
  }

  header {
    background: #0d1226;
    border-bottom: 1px solid #1e3a5f;
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  header h1 {
    font-size: 1.4rem;
    color: #4fc3f7;
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  .live-badge {
    background: #1a3a1a;
    border: 1px solid #4caf50;
    color: #4caf50;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    letter-spacing: 2px;
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
  }

  .container { padding: 24px 32px; }

  /* Stat Cards */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-card {
    background: #0d1226;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
  }

  .stat-card.attack { border-color: #f44336; }
  .stat-card.safe   { border-color: #4caf50; }
  .stat-card.info   { border-color: #4fc3f7; }

  .stat-value {
    font-size: 2.5rem;
    font-weight: bold;
    color: #4fc3f7;
    display: block;
  }

  .stat-card.attack .stat-value { color: #f44336; }
  .stat-card.safe   .stat-value { color: #4caf50; }

  .stat-label {
    font-size: 0.75rem;
    color: #7a8aaa;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
  }

  /* Charts Row */
  .charts-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }

  .card {
    background: #0d1226;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 20px;
  }

  .card h3 {
    font-size: 0.8rem;
    color: #7a8aaa;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 16px;
    border-bottom: 1px solid #1e3a5f;
    padding-bottom: 8px;
  }

  /* Detection Feed */
  .feed-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .feed-table th {
    text-align: left;
    color: #7a8aaa;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 12px;
    border-bottom: 1px solid #1e3a5f;
  }

  .feed-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #0a0e1a;
  }

  .feed-table tr:hover { background: #111827; }

  .badge {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: bold;
    text-transform: uppercase;
  }

  .badge.normal  { background: #1a3a1a; color: #4caf50; }
  .badge.flood   { background: #3a1a1a; color: #f44336; }
  .badge.spoof   { background: #3a2a1a; color: #ff9800; }
  .badge.anomaly { background: #2a1a3a; color: #9c27b0; }

  .new-row {
    animation: highlight 2s ease-out;
  }

  @keyframes highlight {
    0%   { background: #1e3a5f; }
    100% { background: transparent; }
  }

  canvas { max-height: 250px; }
</style>
</head>
<body>

<header>
  <h1>🛡 IoT IDS — Live Security Monitor</h1>
  <div style="display:flex; align-items:center; gap:16px;">
    <span style="color:#7a8aaa; font-size:0.85rem;" id="last-update">Waiting for data...</span>
    <span class="live-badge">● LIVE</span>
  </div>
</header>

<div class="container">

  <!-- Stat Cards -->
  <div class="stats-grid">
    <div class="stat-card info">
      <span class="stat-value" id="stat-total">0</span>
      <span class="stat-label">Total Detections</span>
    </div>
    <div class="stat-card attack">
      <span class="stat-value" id="stat-attacks">0</span>
      <span class="stat-label">Attacks Detected</span>
    </div>
    <div class="stat-card safe">
      <span class="stat-value" id="stat-normal">0</span>
      <span class="stat-label">Normal Traffic</span>
    </div>
    <div class="stat-card info">
      <span class="stat-value" id="stat-devices">0</span>
      <span class="stat-label">Active Devices</span>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-grid">
    <div class="card">
      <h3>Detection Timeline</h3>
      <canvas id="timeline-chart"></canvas>
    </div>
    <div class="card">
      <h3>Attack Distribution</h3>
      <canvas id="pie-chart"></canvas>
    </div>
  </div>

  <!-- Live Feed -->
  <div class="card">
    <h3>Live Detection Feed</h3>
    <table class="feed-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Device</th>
          <th>Prediction</th>
          <th>Confidence</th>
          <th>Avg Temp</th>
          <th>Avg Interval</th>
        </tr>
      </thead>
      <tbody id="feed-body"></tbody>
    </table>
  </div>

</div>

<script>
// ─────────────────────────────────────────
// Chart Setup
// ─────────────────────────────────────────
const timelineCtx = document.getElementById("timeline-chart").getContext("2d");
const pieCtx      = document.getElementById("pie-chart").getContext("2d");

const timelineData = {
  labels  : [],
  datasets: [
    { label: "Normal",  data: [], borderColor: "#4caf50", backgroundColor: "rgba(76,175,80,0.1)",  tension: 0.4, fill: true },
    { label: "Flood",   data: [], borderColor: "#f44336", backgroundColor: "rgba(244,67,54,0.1)",  tension: 0.4, fill: true },
    { label: "Spoof",   data: [], borderColor: "#ff9800", backgroundColor: "rgba(255,152,0,0.1)",  tension: 0.4, fill: true },
    { label: "Anomaly", data: [], borderColor: "#9c27b0", backgroundColor: "rgba(156,39,176,0.1)", tension: 0.4, fill: true }
  ]
};

const timelineChart = new Chart(timelineCtx, {
  type: "line",
  data: timelineData,
  options: {
    responsive    : true,
    animation     : false,
    plugins       : { legend: { labels: { color: "#e0e6f0", font: { size: 11 } } } },
    scales        : {
      x: { ticks: { color: "#7a8aaa" }, grid: { color: "#1e3a5f" } },
      y: { ticks: { color: "#7a8aaa" }, grid: { color: "#1e3a5f" }, beginAtZero: true }
    }
  }
});

const pieChart = new Chart(pieCtx, {
  type: "doughnut",
  data: {
    labels  : ["Normal", "Flood", "Spoof", "Anomaly"],
    datasets: [{
      data           : [0, 0, 0, 0],
      backgroundColor: ["#4caf50", "#f44336", "#ff9800", "#9c27b0"],
      borderColor    : "#0a0e1a",
      borderWidth    : 2
    }]
  },
  options: {
    responsive: true,
    plugins   : { legend: { labels: { color: "#e0e6f0" } } }
  }
});

// ─────────────────────────────────────────
// Timeline tracking
// ─────────────────────────────────────────
let timelineCounts = { normal: 0, flood: 0, spoof: 0, anomaly: 0 };
let lastLabel      = "";

function updateTimeline(prediction, timestamp) {
  timelineCounts[prediction] = (timelineCounts[prediction] || 0) + 1;

  if (timestamp !== lastLabel) {
    lastLabel = timestamp;
    if (timelineData.labels.length > 20) {
      timelineData.labels.shift();
      timelineData.datasets.forEach(d => d.data.shift());
    }
    timelineData.labels.push(timestamp);
    timelineData.datasets[0].data.push(timelineCounts.normal);
    timelineData.datasets[1].data.push(timelineCounts.flood);
    timelineData.datasets[2].data.push(timelineCounts.spoof);
    timelineData.datasets[3].data.push(timelineCounts.anomaly);
    timelineChart.update();
  }
}

// ─────────────────────────────────────────
// Update stat cards
// ─────────────────────────────────────────
function updateStats(stats) {
  document.getElementById("stat-total").textContent   = stats.total;
  document.getElementById("stat-attacks").textContent = stats.attacks;
  document.getElementById("stat-normal").textContent  = stats.normal;
  document.getElementById("stat-devices").textContent = stats.devices;

  pieChart.data.datasets[0].data = [
    stats.normal, stats.flood, stats.spoof, stats.anomaly
  ];
  pieChart.update();
}

// ─────────────────────────────────────────
// Add row to feed table
// ─────────────────────────────────────────
function addFeedRow(d) {
  const tbody = document.getElementById("feed-body");
  const tr    = document.createElement("tr");
  tr.className = "new-row";
  tr.innerHTML = `
    <td>${d.timestamp}</td>
    <td style="color:#4fc3f7">${d.device_id}</td>
    <td><span class="badge ${d.prediction}">${d.prediction}</span></td>
    <td>${(d.confidence * 100).toFixed(1)}%</td>
    <td>${d.mean_temp.toFixed(1)}°C</td>
    <td>${d.mean_interval.toFixed(2)}s</td>
  `;
  tbody.insertBefore(tr, tbody.firstChild);
  if (tbody.rows.length > 20) tbody.deleteRow(tbody.rows.length - 1);
}

// ─────────────────────────────────────────
// SSE Connection
// ─────────────────────────────────────────
const evtSource = new EventSource("/events");

evtSource.onmessage = function(event) {
  const data = JSON.parse(event.data);

  if (data.type === "init") {
    updateStats(data.stats);
    data.detections.forEach(d => addFeedRow(d));
  }

  if (data.type === "detection") {
    updateStats(data.stats);
    addFeedRow(data.detection);
    updateTimeline(data.detection.prediction, data.detection.timestamp);
    document.getElementById("last-update").textContent =
      "Last update: " + data.detection.timestamp;
  }
};

evtSource.onerror = function() {
  document.getElementById("last-update").textContent = "Connection lost — retrying...";
};
</script>

</body>
</html>
"""

# ─────────────────────────────────────────
# Run
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5000")
    print("Dashboard: http://localhost:5000/dashboard")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)