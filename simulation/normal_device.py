import paho.mqtt.client as mqtt
import json
import time
import random
import sys
from datetime import datetime, timezone

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────
BROKER_HOST = "localhost"
BROKER_PORT = 1883
PUBLISH_INTERVAL = 5  # seconds between messages

# Gaussian parameters for realistic sensor values
TEMP_MEAN = 22.0
TEMP_STD  = 1.5
HUM_MEAN  = 60.0
HUM_STD   = 3.0

# ─────────────────────────────────────────
# Device identity (from command line argument)
# ─────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python normal_device.py <device_id>")
    print("Example: python normal_device.py device_01")
    sys.exit(1)

DEVICE_ID = sys.argv[1]
TOPIC     = f"iot/devices/{DEVICE_ID}/data"

# ─────────────────────────────────────────
# MQTT Callbacks
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{DEVICE_ID}] Connected to broker at {BROKER_HOST}:{BROKER_PORT}")
    else:
        print(f"[{DEVICE_ID}] Connection failed with code {rc}")

def on_publish(client, userdata, mid):
    print(f"[{DEVICE_ID}] Message delivered (mid={mid})")

# ─────────────────────────────────────────
# MQTT Client Setup
# ─────────────────────────────────────────
client = mqtt.Client(client_id=DEVICE_ID)
client.on_connect = on_connect
client.on_publish  = on_publish

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()  # runs network loop in background thread

# ─────────────────────────────────────────
# Main Publishing Loop
# ─────────────────────────────────────────
msg_count = 0

print(f"[{DEVICE_ID}] Starting simulation. Publishing every {PUBLISH_INTERVAL}s...")
print(f"[{DEVICE_ID}] Topic: {TOPIC}")
print("-" * 50)

try:
    while True:
        msg_count += 1

        # Generate realistic sensor values
        temperature = round(random.gauss(TEMP_MEAN, TEMP_STD), 2)
        humidity    = round(random.gauss(HUM_MEAN,  HUM_STD),  2)

        # Clamp values to physically plausible range
        temperature = max(10.0, min(40.0, temperature))
        humidity    = max(20.0, min(95.0, humidity))

        # Build payload
        payload = {
            "device_id"    : DEVICE_ID,
            "timestamp"    : datetime.now(timezone.utc).isoformat(),
            "temperature"  : temperature,
            "humidity"     : humidity,
            "msg_count"    : msg_count,
            "payload_size" : 0  # will be updated below
        }

        # Calculate actual payload size
        payload_str          = json.dumps(payload)
        payload["payload_size"] = len(payload_str.encode("utf-8"))
        payload_str          = json.dumps(payload)  # rebuild with correct size

        # Publish
        result = client.publish(TOPIC, payload_str, qos=0)

        print(f"[{DEVICE_ID}] msg#{msg_count:04d} | "
              f"temp={temperature:.2f}°C | "
              f"hum={humidity:.2f}% | "
              f"size={payload['payload_size']}B")

        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[{DEVICE_ID}] Simulation stopped by user.")
    client.loop_stop()
    client.disconnect()