from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import paho.mqtt.client as mqtt
import json

from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/summit_safeguard'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this'  # Ganti dengan kunci rahasia yang kuat

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Dekorator Kustom ---
def penyelamat_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'penyelamat':
            flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- Model Database ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(80), nullable=False)  # 'penyelamat' atau 'viewer'
    id_pendaki_terkait = db.Column(db.String(50), nullable=True)  # Hanya untuk role 'viewer'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class PendakiData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_pendaki = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    suhu = db.Column(db.Float)
    kelembaban = db.Column(db.Float)
    sos = db.Column('status_sos', db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<PendakiData {self.id_pendaki}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Inisialisasi Database & User Awal ---

def create_initial_users():
    with app.app_context():
        db.create_all()
        # User Penyelamat
        if not User.query.filter_by(username='penyelamat1').first():
            penyelamat = User(username='penyelamat1', role='penyelamat')
            penyelamat.set_password('password123')
            db.session.add(penyelamat)
            print("User 'penyelamat1' dibuat.")

        # User Viewer
        if not User.query.filter_by(username='keluarga1').first():
            viewer = User(username='keluarga1', role='viewer', id_pendaki_terkait='1')
            viewer.set_password('password123')
            db.session.add(viewer)
            print("User 'keluarga1' dibuat.")
        
        db.session.commit()

# --- Logika MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe("tracking/+/data")

def on_message(client, userdata, msg):
    with app.app_context():
        try:
            topic_parts = msg.topic.split('/')
            id_pendaki = topic_parts[1]
            data = json.loads(msg.payload.decode('utf-8'))
            
            new_data = PendakiData(
                id_pendaki=id_pendaki,
                latitude=data['latitude'],
                longitude=data['longitude'],
                suhu=data['suhu'],
                kelembaban=data['kelembaban'],
                sos=data.get('sos', 0)
            )
            db.session.add(new_data)
            db.session.commit()
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)
client.loop_start()

# --- Rute Autentikasi ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'penyelamat':
            return redirect(url_for('home'))
        else:
            return redirect(url_for('dashboard', id_pendaki=current_user.id_pendaki_terkait))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Login berhasil!', 'success')
            if user.role == 'penyelamat':
                return redirect(url_for('home'))
            elif user.role == 'viewer':
                return redirect(url_for('dashboard', id_pendaki=user.id_pendaki_terkait))
        else:
            flash('Username atau password salah.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

# --- Rute Aplikasi ---

@app.route('/')
@login_required
def home():
    if current_user.role == 'viewer':
        return redirect(url_for('dashboard', id_pendaki=current_user.id_pendaki_terkait))
    
    pendaki_aktif = PendakiData.query.with_entities(PendakiData.id_pendaki).distinct().all()
    pendaki_list = [p[0] for p in pendaki_aktif]
    return render_template('home.html', pendaki_list=pendaki_list)

@app.route('/dashboard/<id_pendaki>')
@login_required
def dashboard(id_pendaki):
    if current_user.role == 'viewer' and current_user.id_pendaki_terkait != id_pendaki:
        flash('Anda tidak memiliki akses ke dashboard ini.', 'danger')
        return redirect(url_for('dashboard', id_pendaki=current_user.id_pendaki_terkait))
    
    return render_template('dashboard.html', selected_pendaki=id_pendaki)

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

# --- Rute Manajemen User ---

@app.route('/manage-users', methods=['GET', 'POST'])
@login_required
@penyelamat_required
def manage_users():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        id_pendaki_terkait = request.form.get('id_pendaki_terkait')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username sudah ada.', 'danger')
            return redirect(url_for('manage_users'))

        new_user = User(
            username=username,
            role=role,
            id_pendaki_terkait=id_pendaki_terkait if role == 'viewer' else None
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('User baru berhasil ditambahkan.', 'success')
        return redirect(url_for('manage_users'))

    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/edit-user/<int:id>', methods=['GET', 'POST'])
@login_required
@penyelamat_required
def edit_user(id):
    user_to_edit = User.query.get_or_404(id)
    if request.method == 'POST':
        user_to_edit.username = request.form['username']
        user_to_edit.role = request.form['role']
        user_to_edit.id_pendaki_terkait = request.form.get('id_pendaki_terkait') if user_to_edit.role == 'viewer' else None
        
        new_password = request.form.get('password')
        if new_password:
            user_to_edit.set_password(new_password)
        
        db.session.commit()
        flash('Data user berhasil diperbarui.', 'success')
        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user_to_edit)

@app.route('/delete-user/<int:id>', methods=['POST'])
@login_required
@penyelamat_required
def delete_user(id):
    if id == current_user.id:
        flash('Anda tidak bisa menghapus akun Anda sendiri.', 'danger')
        return redirect(url_for('manage_users'))

    user_to_delete = User.query.get_or_404(id)
    db.session.delete(user_to_delete)
    db.session.commit()
    flash('User berhasil dihapus.', 'success')
    return redirect(url_for('manage_users'))


@app.route('/api/data/<id_pendaki>')
@login_required
def get_data(id_pendaki):
    if current_user.role == 'viewer' and current_user.id_pendaki_terkait != id_pendaki:
        return jsonify({'error': 'Akses ditolak'}), 403

    latest_data = PendakiData.query.filter_by(id_pendaki=id_pendaki).order_by(PendakiData.timestamp.desc()).limit(10).all()
    data_list = [{'id_pendaki': item.id_pendaki, 'latitude': item.latitude, 'longitude': item.longitude, 'suhu': item.suhu, 'kelembaban': item.kelembaban, 'sos': item.sos, 'timestamp': item.timestamp.isoformat()} for item in latest_data]
    return jsonify(data_list)

if __name__ == '__main__':
    create_initial_users()
    app.run(debug=True)