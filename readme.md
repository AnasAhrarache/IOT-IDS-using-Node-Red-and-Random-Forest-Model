# IoT Intrusion Detection System — MQTT & Machine Learning

A fully simulated Intrusion Detection System (IDS) for an MQTT-based IoT network. Detects four traffic classes in real time using a Random Forest classifier trained on behavioral features extracted by Node-RED.

**Accuracy: 100% on test set | Latency: ~30s | 0 False Negatives**

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Attack Types](#attack-types)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the System](#running-the-system)
- [Dashboard](#dashboard)
- [ML Model](#ml-model)
- [Team](#team)

---

## Overview

Standard network-level IDS tools are poorly suited to IoT environments — they require packet-level access, are too resource-heavy for constrained devices, and miss application-layer MQTT attacks. This project takes a different approach: extract **behavioral features** directly from MQTT message flows (accessible from any gateway or application server), feed them into a trained classifier, and alert in real time.

| Component | Technology |
|-----------|-----------|
| Simulators | Python + paho-mqtt |
| MQTT Broker | Mosquitto 2.1.2 |
| Orchestration | Node-RED v4.1.10 |
| ML API | Flask + scikit-learn |
| Classifier | Random Forest (100 trees) |
| Dashboard | Flask + SSE (real-time push) |

---

## Architecture

```
Python Simulators
  normal_device.py  ──┐
  attacker_flood.py ──┤   MQTT publish
  attacker_spoof.py ──┤──► Mosquitto :1883
  attacker_anomaly  ──┘
                              │
                              ▼
                        Node-RED :1880
                     (feature extraction)
                              │
                      POST /predict
                              │
                              ▼
                        Flask API :5000
                      (Random Forest)
                              │
                    ┌─────────┴─────────┐
                  ALERT             NORMAL
                              │
                              ▼
                       Dashboard :5000
                    (real-time monitoring)
```

**Detection pipeline per device:**
1. Node-RED receives MQTT messages and buffers them in a 30-second sliding window per `device_id`
2. At each window, 10 behavioral features are computed
3. Features are POST'd to the Flask `/predict` endpoint
4. Random Forest returns a prediction + confidence score
5. Node-RED routes the result to ALERT or NORMAL
6. Dashboard updates via Server-Sent Events (SSE)

---

## Attack Types

| Class | Behavior | Key signature |
|-------|----------|---------------|
| `normal` | Temperature ~22°C (Gaussian), humidity ~60%, interval 5s | Baseline |
| `flood` | Same values as normal but interval **4s** instead of 5s | `mean_interval` ↓ |
| `spoof` | Temperature fixed at **87°C**, humidity **5%** | `mean_temp`, `out_of_range_ratio` ↑ |
| `anomaly` | Temperature 34–39°C, humidity 21–26% | Statistical drift in sensor values |

Attacks are intentionally subtle — no threshold rule can reliably catch them. The model detects them through learned behavioral patterns.

---

## Project Structure

```
IOT IDS/
├── mosquitto.conf              # Broker configuration
│
├── simulation/
│   ├── normal_device.py        # Legitimate IoT device simulator
│   ├── attacker_flood.py       # Flooding attack simulator
│   ├── attacker_spoof.py       # Spoofing attack simulator
│   └── attacker_anomaly.py     # Anomalous payload simulator
│
├── model/
│   ├── collect_data.py         # Dataset collection script
│   ├── training_data.csv       # 513 labeled 30s windows
│   ├── train_model_final.ipynb # Training notebook
│   ├── random_forest.pkl       # Trained model (joblib)
│   ├── label_encoder.pkl       # Label encoder (joblib)
│   └── features.json           # Ordered feature names
│
├── api/
│   └── app.py                  # Flask API + live dashboard
│
└── nodered/
    ├── flows.json              # Node-RED flow export
    └── README.md               # Import instructions
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- [Mosquitto](https://mosquitto.org/download/) 2.x
- Node-RED: `npm install -g node-red`

Install Python dependencies:

```bash
pip install paho-mqtt flask scikit-learn pandas numpy joblib
```

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/iot-ids-mqtt.git
cd iot-ids-mqtt
```

**2. Configure Mosquitto**

The `mosquitto.conf` at the root is already configured for local use:

```
listener 1883 localhost
allow_anonymous true
```

**3. Import the Node-RED flow**

Start Node-RED, open `http://localhost:1880`, then:
Menu (≡) → Import → select `nodered/flows.json` → Deploy

The model files (`random_forest.pkl`, `label_encoder.pkl`, `features.json`) are included in `model/` — no retraining needed to run the system.

---

## Running the System

Open **5 terminals** and run each command in order:

```bash
# Terminal 1 — MQTT Broker
"C:\Program Files\mosquitto\mosquitto.exe" -c "mosquitto.conf" -v

# Terminal 2 — Flask ML API
cd api
python app.py

# Terminal 3 — Node-RED (then deploy the flow at http://localhost:1880)
node-red

# Terminal 4 — Normal device simulator
cd simulation
python normal_device.py device1

# Terminal 5 — Attack simulator (choose one)
python attacker_flood.py device2
# OR
python attacker_spoof.py device2
# OR
python attacker_anomaly.py device2
```

**Ports summary:**

| Service | Port |
|---------|------|
| Mosquitto (MQTT) | 1883 |
| Node-RED editor | 1880 |
| Flask API + Dashboard | 5000 |

---

## Dashboard

Open `http://localhost:5000/dashboard` after starting the Flask API.

Features:
- **4 stat cards** — total detections, attacks detected, normal traffic, active devices
- **Detection timeline** — cumulative chart per class (Normal / Flood / Spoof / Anomaly)
- **Attack distribution** — doughnut chart
- **Live feed** — last 20 detections with timestamp, device, prediction badge, confidence score

Updates are pushed in real time via SSE — no page refresh needed.

---

## ML Model

### Dataset

Generated directly from the simulators using `model/collect_data.py`.

| Class | Windows | Collection time |
|-------|---------|-----------------|
| normal | 129 | 20 min |
| flood | 138 | 20 min |
| spoof | 126 | 20 min |
| anomaly | 120 | 20 min |
| **Total** | **513** | **80 min** |

Public datasets (MQTT-IoT-IDS2020, MQTTEEB-D) were evaluated and rejected — they use TCP/IP-level features inaccessible from Node-RED. Training on what you actually measure in production is a hard requirement for a valid model.

### Features (10 behavioral, 30s window per device)

| # | Feature | Description |
|---|---------|-------------|
| 1 | `msg_count` | Number of messages in window |
| 2 | `mean_interval` | Average publish interval (s) |
| 3 | `std_interval` | Std dev of intervals |
| 4 | `mean_payload_size` | Average payload size (bytes) |
| 5 | `mean_temp` | Average temperature |
| 6 | `std_temp` | Std dev of temperature |
| 7 | `mean_humidity` | Average humidity |
| 8 | `std_humidity` | Std dev of humidity |
| 9 | `out_of_range_ratio` | Fraction of physically impossible values |
| 10 | `topic_depth` | MQTT topic hierarchy depth |

### Results

| Class | Precision | Recall | F1 |
|-------|-----------|--------|----|
| anomaly | 1.00 | 1.00 | 1.00 |
| flood | 1.00 | 1.00 | 1.00 |
| normal | 1.00 | 1.00 | 1.00 |
| spoof | 1.00 | 1.00 | 1.00 |

Test set: 103 samples (80/20 stratified split). 0 false negatives, 0 false positives.

Top features by importance: `mean_payload_size` (19.8%), `mean_interval` (19.3%), `mean_humidity` (15.9%), `mean_temp` (14.5%).

---

## Team

| Name | Institution |
|------|------------|
| Ahrarache Anas | FST Tanger — Université Abdelmalek Essaâdi |
| Mohamed Ait Ezzaouite | FST Tanger — Université Abdelmalek Essaâdi |
| Nadir Mounim | FST Tanger — Université Abdelmalek Essaâdi |

**Module:** Internet of Things (IoT) — Pr. M. EL BRAK
**Academic year:** 2025/2026