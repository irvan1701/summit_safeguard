# app.py

from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/summit_safeguard'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class PendakiData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_pendaki = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    suhu = db.Column(db.Float)
    kelembaban = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<PendakiData {self.id_pendaki}>'

with app.app_context():
    db.create_all()

# --- Logika MQTT (Sama seperti sebelumnya) ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe("tracking/+/data")
    print("Subscribed to topic: tracking/+/data")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        id_pendaki = topic_parts[1]
        
        data_json = msg.payload.decode('utf-8')
        data = json.loads(data_json)
        
        print(f"Received data from {id_pendaki}: {data}")

        new_data = PendakiData(
            id_pendaki=id_pendaki,
            latitude=data['latitude'],
            longitude=data['longitude'],
            suhu=data['suhu'],
            kelembaban=data['kelembaban']
        )
        db.session.add(new_data)
        db.session.commit()
        print("Data saved to database!")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)
client.loop_start()

# --- Rute Flask Baru ---

# Rute halaman utama: menampilkan daftar pendaki
@app.route('/')
def home():
    pendaki_aktif = PendakiData.query.with_entities(PendakiData.id_pendaki).distinct().all()
    pendaki_list = [p[0] for p in pendaki_aktif]
    return render_template('home.html', pendaki_list=pendaki_list)

# Rute dashboard per pendaki
@app.route('/dashboard/<id_pendaki>')
def dashboard(id_pendaki):
    return render_template('dashboard.html', selected_pendaki=id_pendaki)




# API untuk mendapatkan data pendaki tertentu
@app.route('/api/data/<id_pendaki>')
def get_data(id_pendaki):
    latest_data = PendakiData.query.filter_by(id_pendaki=id_pendaki).order_by(PendakiData.timestamp.desc()).limit(10).all()
    
    data_list = []
    for item in latest_data:
        data_list.append({
            'id_pendaki': item.id_pendaki,
            'latitude': item.latitude,
            'longitude': item.longitude,
            'suhu': item.suhu,
            'kelembaban': item.kelembaban,
            'timestamp': item.timestamp.isoformat()
        })
    return jsonify(data_list)

if __name__ == '__main__':
    app.run(debug=True)