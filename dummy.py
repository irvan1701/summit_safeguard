# mqtt_publisher_dummy.py

import paho.mqtt.client as mqtt
import json
import time
import random

# Konfigurasi Broker MQTT
broker_address = "broker.mqtt-dashboard.com"
broker_port = 1883

# Daftar pendaki yang akan disimulasikan
pendaki_list = ["pendaki_01", "pendaki_02"]

# Data awal (simulasi lokasi)
locations = {
    "pendaki_01": {"lat": -6.2146, "long": 106.8451},
    "pendaki_02": {"lat": -6.5971, "long": 106.8066}
}

# Inisialisasi MQTT Client
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")

client.on_connect = on_connect

# Menghubungkan ke broker
client.connect(broker_address, broker_port, 60)
client.loop_start()

print("Mulai mengirim data dummy...")

try:
    while True:
        # Loop untuk setiap pendaki
        for pendaki_id in pendaki_list:
            # Simulasi pergerakan lokasi secara acak
            locations[pendaki_id]["lat"] += random.uniform(-0.0005, 0.0005)
            locations[pendaki_id]["long"] += random.uniform(-0.0005, 0.0005)

            # Simulasi data sensor
            data = {
                "latitude": round(locations[pendaki_id]["lat"], 8),
                "longitude": round(locations[pendaki_id]["long"], 8),
                "suhu": round(random.uniform(20.0, 30.0), 2),
                "kelembaban": round(random.uniform(60.0, 80.0), 2),
                "status_sos": 0 if random.random() < 0.5 else 1 # 10% kemungkinan SOS aktif
            }

            # Topik pengiriman data
            topic = f"tracking/{pendaki_id}/data"

            # Mengirim data ke broker dalam format JSON
            client.publish(topic, json.dumps(data))
            print(f"Sent data for {pendaki_id} to topic '{topic}' with SOS status: {data['status_sos']}")

        # Jeda 5 detik sebelum mengirim data berikutnya
        time.sleep(5)

except KeyboardInterrupt:
    print("Pengiriman data dihentikan.")
    client.loop_stop()
    client.disconnect()