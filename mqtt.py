# mqtt_subscriber.py

import paho.mqtt.client as mqtt
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
import time

# --- Konfigurasi Database ---
DATABASE_URL = 'mysql+pymysql://root:@localhost/summit_safeguard'

# --- Inisialisasi Database SQLAlchemy ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Model Database ---
class PendakiData(Base):
    __tablename__ = 'pendaki_data'
    id = Column(Integer, primary_key=True, index=True)
    id_pendaki = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    suhu = Column(Float)
    kelembaban = Column(Float)
    status_sos = Column(Integer, default=0) # Kolom untuk status SOS
    timestamp = Column(DateTime, default=func.current_timestamp())

# Pastikan tabel dibuat di database jika belum ada
Base.metadata.create_all(bind=engine)

# --- Logika MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe("tracking/+/data")
    print("Subscribed to topic: tracking/+/data")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        if len(topic_parts) >= 2:
            id_pendaki = topic_parts[1]
        else:
            print("Error: Invalid topic format.")
            return

        data_json = msg.payload.decode('utf-8')
        data = json.loads(data_json)
        
        print(f"Received data from {id_pendaki}: {data}")

        # Simpan data ke database
        db = SessionLocal()
        new_data = PendakiData(
            id_pendaki=id_pendaki,
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            suhu=data.get('suhu'),
            kelembaban=data.get('kelembaban'),
            status_sos=data.get('status_sos', 0) # Ambil status_sos, default 0 jika tidak ada
        )
        db.add(new_data)
        db.commit()
        db.close()
        print(f"Data for {id_pendaki} saved to database!")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")

# Inisialisasi dan koneksi ke broker MQTT
if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Menghubungkan ke broker dengan loop yang akan terus berjalan
    while True:
        try:
            client.connect("broker.mqtt-dashboard.com", 1883, 60)
            client.loop_forever()
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)