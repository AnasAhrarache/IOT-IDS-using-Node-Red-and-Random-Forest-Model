import paho.mqtt.client as mqtt
import json
import csv
import time
import numpy as np
import sys
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────
BROKER_HOST   = "localhost"
BROKER_PORT   = 1883
WINDOW_SIZE   = 30    # seconds per feature window
OUTPUT_FILE   = "D:/IOT IDS/model/training_data.csv"

# Label from command line
if len(sys.argv) < 2:
    print("Usage: python collect_data.py <label>")
    print("Labels: normal, flood, spoof, anomaly")
    sys.exit(1)

LABEL = sys.argv[1]
if LABEL not in ["normal", "flood", "spoof", "anomaly"]:
    print(f"Invalid label: {LABEL}")
    print("Must be one of: normal, flood, spoof, anomaly")
    sys.exit(1)

# ─────────────────────────────────────────
# Per-device message buffer
# ─────────────────────────────────────────
device_buffers = defaultdict(list)  # device_id → list of messages

# ─────────────────────────────────────────
# CSV Setup
# ─────────────────────────────────────────
FEATURE_NAMES = [
    "msg_count", "mean_interval", "std_interval",
    "mean_payload_size", "mean_temp", "std_temp",
    "mean_humidity", "std_humidity",
    "out_of_range_ratio", "topic_depth", "label"
]

# Write header if file doesn't exist
import os
write_header = not os.path.exists(OUTPUT_FILE)
csv_file = open(OUTPUT_FILE, "a", newline="")
writer = csv.DictWriter(csv_file, fieldnames=FEATURE_NAMES)
if write_header:
    writer.writeheader()
    csv_file.flush()

# ─────────────────────────────────────────
# Feature Extraction
# ─────────────────────────────────────────
def extract_features(device_id, messages):
    """
    Given a list of messages from one device in one window,
    compute behavioral features.
    """
    if len(messages) < 2:
        return None  # not enough data for this window

    # Message count
    msg_count = len(messages)

    # Inter-message intervals
    timestamps = [m["timestamp"] for m in messages]
    intervals  = [timestamps[i+1] - timestamps[i] 
                  for i in range(len(timestamps)-1)]
    mean_interval = np.mean(intervals)
    std_interval  = np.std(intervals)

    # Payload sizes
    sizes = [m["payload_size"] for m in messages]
    mean_payload_size = np.mean(sizes)

    # Temperature
    temps     = [m["temperature"] for m in messages]
    mean_temp = np.mean(temps)
    std_temp  = np.std(temps)

    # Humidity
    hums          = [m["humidity"] for m in messages]
    mean_humidity = np.mean(hums)
    std_humidity  = np.std(hums)

    # Out of range ratio
    out_of_range = sum(
        1 for m in messages
        if m["temperature"] < 10 or m["temperature"] > 40
        or m["humidity"] < 20 or m["humidity"] > 95
    )
    out_of_range_ratio = out_of_range / msg_count

    # Topic depth — same for all messages from same device
    topic_depth = messages[0]["topic_depth"]

    return {
        "msg_count"          : msg_count,
        "mean_interval"      : round(mean_interval, 4),
        "std_interval"       : round(std_interval, 4),
        "mean_payload_size"  : round(mean_payload_size, 2),
        "mean_temp"          : round(mean_temp, 2),
        "std_temp"           : round(std_temp, 4),
        "mean_humidity"      : round(mean_humidity, 2),
        "std_humidity"       : round(std_humidity, 4),
        "out_of_range_ratio" : round(out_of_range_ratio, 4),
        "topic_depth"        : topic_depth,
        "label"              : LABEL
    }

# ─────────────────────────────────────────
# MQTT Callbacks
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("iot/devices/#")
        print(f"[COLLECTOR] Connected. Subscribed to iot/devices/#")
        print(f"[COLLECTOR] Collecting label: {LABEL}")
        print(f"[COLLECTOR] Window size: {WINDOW_SIZE}s")
        print(f"[COLLECTOR] Output: {OUTPUT_FILE}")
        print("-" * 50)
    else:
        print(f"[COLLECTOR] Connection failed: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        device_id = payload.get("device_id", "unknown")

        # Add arrival timestamp and topic depth
        payload["timestamp"]   = time.time()
        payload["topic_depth"] = len(msg.topic.split("/"))

        device_buffers[device_id].append(payload)

    except Exception as e:
        print(f"[COLLECTOR] Error parsing message: {e}")

# ─────────────────────────────────────────
# MQTT Client Setup
# ─────────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, 
                     client_id="data_collector")
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# ─────────────────────────────────────────
# Main Collection Loop
# ─────────────────────────────────────────
windows_collected = 0
print(f"[COLLECTOR] Starting. Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(WINDOW_SIZE)

        # Process each device's buffer
        for device_id, messages in list(device_buffers.items()):
            if len(messages) < 2:
                continue

            features = extract_features(device_id, messages)

            if features:
                writer.writerow(features)
                csv_file.flush()
                windows_collected += 1
                print(f"[COLLECTOR] Window #{windows_collected:04d} | "
                      f"device={device_id} | "
                      f"msgs={features['msg_count']} | "
                      f"interval={features['mean_interval']}s | "
                      f"temp={features['mean_temp']}°C | "
                      f"label={LABEL}")

        # Clear buffers for next window
        device_buffers.clear()

except KeyboardInterrupt:
    print(f"\n[COLLECTOR] Stopped.")
    print(f"[COLLECTOR] Total windows collected: {windows_collected}")
    csv_file.close()
    client.loop_stop()
    client.disconnect()