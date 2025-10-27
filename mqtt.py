# mqtt_subscriber.py

import paho.mqtt.client as mqtt
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
import time
import re

# --- Konfigurasi Database (GANTI JIKA PERLU) ---
DATABASE_URL = 'mysql+pymysql://root:@localhost/summit_safeguard'

# --- Inisialisasi SQLAlchemy ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Model Database ---
class PendakiData(Base):
    __tablename__ = 'pendaki_data'
    id = Column(Integer, primary_key=True, index=True)
    id_pendaki = Column(String(50), nullable=False)
    # Sesuaikan dengan tipe data di MySQL (Float di SQLAlchemy akan handle DECIMAL)
    latitude = Column(Float, nullable=False) 
    longitude = Column(Float, nullable=False)
    suhu = Column(Float) 
    kelembaban = Column(Float)
    status_sos = Column(Integer, default=0)
    timestamp = Column(DateTime, default=func.current_timestamp())

try:
    Base.metadata.create_all(bind=engine)
    print("Database table 'pendaki_data' verified/created successfully.")
except Exception as e:
    print(f"ERROR: Could not connect to database or create table. {e}")


# --- Logika MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    # Berlangganan (Subscribe) ke semua ID pendaki
    client.subscribe("tracking/+/data") 
    print("Subscribed to topic: tracking/+/data")

def on_message(client, userdata, msg):
    try:
        # 1. Ekstrak ID Pendaki dari Topik
        topic_parts = msg.topic.split('/')
        # Validasi format ID yang diharapkan: "pendaki_ANGKA"
        if len(topic_parts) >= 2 and re.match(r'^pendaki_\d+$', topic_parts[1]):
            id_pendaki = topic_parts[1]
        else:
            print(f"Error: Invalid topic format or ID not recognized: {msg.topic}")
            return

        # 2. Urai Payload JSON
        data_json = msg.payload.decode('utf-8')
        data = json.loads(data_json)
        
        print(f"Received data from {id_pendaki}: {data}")

        # 3. Simpan data ke database
        db = SessionLocal()
        new_data = PendakiData(
            id_pendaki=id_pendaki,
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            suhu=data.get('suhu'),          
            kelembaban=data.get('kelembaban'),
            status_sos=data.get('status_sos', 0)
        )
        db.add(new_data)
        db.commit()
        db.close()
        print(f"Data for {id_pendaki} successfully saved to database!")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")
        # Tangani error database
        if 'db' in locals() and db.is_active:
            db.rollback()
            db.close()

# --- Inisialisasi dan Koneksi ---
if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    while True:
        try:
            client.connect("broker.mqtt-dashboard.com", 1883, 60)
            client.loop_forever() # Loop dan tunggu pesan
        except Exception as e:
            print(f"Connection to MQTT broker failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)