import paho.mqtt.client as mqtt
import json
import time
import random
import sys
from datetime import datetime, timezone

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────
BROKER_HOST      = "localhost"
BROKER_PORT      = 1883
PUBLISH_INTERVAL = 5

# Anomalous ranges — valid but statistically deviant
# Normal temp mean=22, std=1.5 → range roughly 18–26°C
# Anomalous temp: consistently 34–39°C (high but not impossible)
ANOMALY_TEMP_MIN = 34.0
ANOMALY_TEMP_MAX = 39.0

# Normal humidity mean=60, std=3 → range roughly 50–70%
# Anomalous humidity: consistently 21–26% (very dry but not impossible)
ANOMALY_HUM_MIN  = 21.0
ANOMALY_HUM_MAX  = 26.0

# ─────────────────────────────────────────
# Device identity
# ─────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python attacker_anomaly.py <device_id>")
    print("Example: python attacker_anomaly.py device_03")
    sys.exit(1)

DEVICE_ID = sys.argv[1]
TOPIC     = f"iot/devices/{DEVICE_ID}/data"

# ─────────────────────────────────────────
# MQTT Callbacks
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[ANOMALY ATTACKER | {DEVICE_ID}] Connected to broker")
    else:
        print(f"[ANOMALY ATTACKER | {DEVICE_ID}] Connection failed: {rc}")

# ─────────────────────────────────────────
# MQTT Client Setup
# ─────────────────────────────────────────
client = mqtt.Client(client_id=f"attacker_anomaly_{DEVICE_ID}")
client.on_connect = on_connect

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# ─────────────────────────────────────────
# Main Publishing Loop
# ─────────────────────────────────────────
msg_count = 0

print(f"[ANOMALY ATTACKER] Targeting device: {DEVICE_ID}")
print(f"[ANOMALY ATTACKER] Temp range: {ANOMALY_TEMP_MIN}–{ANOMALY_TEMP_MAX}°C")
print(f"[ANOMALY ATTACKER] Hum range:  {ANOMALY_HUM_MIN}–{ANOMALY_HUM_MAX}%")
print("-" * 50)

try:
    while True:
        msg_count += 1

        temperature = round(random.uniform(ANOMALY_TEMP_MIN, ANOMALY_TEMP_MAX), 2)
        humidity    = round(random.uniform(ANOMALY_HUM_MIN,  ANOMALY_HUM_MAX),  2)

        payload = {
            "device_id"   : DEVICE_ID,
            "timestamp"   : datetime.now(timezone.utc).isoformat(),
            "temperature" : temperature,
            "humidity"    : humidity,
            "msg_count"   : msg_count,
            "payload_size": 0,
            "attack_type" : "anomaly"
        }

        payload_str             = json.dumps(payload)
        payload["payload_size"] = len(payload_str.encode("utf-8"))
        payload_str             = json.dumps(payload)

        client.publish(TOPIC, payload_str, qos=0)

        print(f"[ANOMALY | {DEVICE_ID}] msg#{msg_count:04d} | "
              f"temp={temperature:.2f}°C | "
              f"hum={humidity:.2f}%")

        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[ANOMALY ATTACKER] Stopped.")
    client.loop_stop()
    client.disconnect()