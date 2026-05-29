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
PUBLISH_INTERVAL = 4  # faster than normal (5s) — subtle flood

TEMP_MEAN = 22.0
TEMP_STD  = 1.5
HUM_MEAN  = 60.0
HUM_STD   = 3.0

# ─────────────────────────────────────────
# Device identity
# ─────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python attacker_flood.py <device_id>")
    print("Example: python attacker_flood.py device_01")
    sys.exit(1)

DEVICE_ID = sys.argv[1]
TOPIC     = f"iot/devices/{DEVICE_ID}/data"

# ─────────────────────────────────────────
# MQTT Callbacks
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[FLOOD ATTACKER | {DEVICE_ID}] Connected to broker")
    else:
        print(f"[FLOOD ATTACKER | {DEVICE_ID}] Connection failed: {rc}")

# ─────────────────────────────────────────
# MQTT Client Setup
# ─────────────────────────────────────────
client = mqtt.Client(client_id=f"attacker_flood_{DEVICE_ID}")
client.on_connect = on_connect

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# ─────────────────────────────────────────
# Main Publishing Loop
# ─────────────────────────────────────────
msg_count = 0

print(f"[FLOOD ATTACKER] Targeting device: {DEVICE_ID}")
print(f"[FLOOD ATTACKER] Publish interval: {PUBLISH_INTERVAL}s (normal=5s)")
print("-" * 50)

try:
    while True:
        msg_count += 1

        temperature = round(random.gauss(TEMP_MEAN, TEMP_STD), 2)
        humidity    = round(random.gauss(HUM_MEAN,  HUM_STD),  2)

        temperature = max(10.0, min(40.0, temperature))
        humidity    = max(20.0, min(95.0, humidity))

        payload = {
            "device_id"   : DEVICE_ID,
            "timestamp"   : datetime.now(timezone.utc).isoformat(),
            "temperature" : temperature,
            "humidity"    : humidity,
            "msg_count"   : msg_count,
            "payload_size": 0,
            "attack_type" : "flood"
        }

        payload_str          = json.dumps(payload)
        payload["payload_size"] = len(payload_str.encode("utf-8"))
        payload_str          = json.dumps(payload)

        client.publish(TOPIC, payload_str, qos=0)

        print(f"[FLOOD | {DEVICE_ID}] msg#{msg_count:04d} | "
              f"temp={temperature:.2f}°C | "
              f"interval={PUBLISH_INTERVAL}s")

        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[FLOOD ATTACKER] Stopped.")
    client.loop_stop()
    client.disconnect()