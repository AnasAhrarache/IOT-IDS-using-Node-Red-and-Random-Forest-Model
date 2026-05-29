# Node-RED — IoT IDS Flow

This folder contains the exported Node-RED flow for the IoT Intrusion Detection System.

## File

| File         | Description                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------- |
| `flows.json` | Complete Node-RED flow — MQTT ingestion, feature extraction, Flask AI API call, alert routing |

## Flow Overview

```
MQTT-in (iot/devices/#)
    └── JSON parser
        └── Feature Extractor (function node)
            └── Flask AI API (HTTP POST → localhost:5000/predict)
                └── Is Attack? (switch node)
                    ├── [true]  → ALERT (debug)
                    └── [false] → NORMAL (debug)
```

The **Feature Extractor** maintains a 30-second sliding window per device and computes 10 behavioral features before forwarding them to the Flask ML API.

## How to Import

1. Start Node-RED:

   ```bash
   node-red
   ```

2. Open the editor at `http://localhost:1880`

3. Click the **hamburger menu (≡)** → **Import**

4. Select `flows.json` → **Import**

5. Click **Deploy**

## Prerequisites

- Node-RED v4.x installed (`npm install -g node-red`)
- Mosquitto broker running on `localhost:1883`
- Flask API running on `localhost:5000` (see `../api/`)

## MQTT Topic

The flow subscribes to the wildcard topic:

```
iot/devices/#
```

This captures messages from all devices regardless of their ID.

## Expected Input (from simulators)

```json
{
  "device_id": "device1",
  "timestamp": "2026-05-29T12:07:21.453Z",
  "temperature": 22.47,
  "humidity": 58.32,
  "payload_size": 149,
  "msg_count": 42
}
```

## Expected Output (from Flask API)

```json
{
  "prediction": "flood",
  "confidence": 0.97,
  "is_attack": true,
  "status": "ok"
}
```

## Notes

- `flows_cred.json` is intentionally excluded — it contains encrypted credentials tied to the local machine.
- Detection latency is minimum **30 seconds** — this is by design (size of the behavioral window).
- Each device has its own independent context in the Feature Extractor node, so multiple devices are tracked simultaneously without interference.
