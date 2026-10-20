import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-this-in-production'

# การตั้งค่าฐานข้อมูล SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checkin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # จำกัดขนาดไฟล์รูปที่ 16MB

db = SQLAlchemy(app)

# มั่นใจว่าโฟลเดอร์อัปโหลดรูปภาพถูกสร้างขึ้น
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class CheckInRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# สร้างตารางข้อมูลและผู้ใช้จำลองเมื่อรันแอปครั้งแรก
with app.app_context():
    db.create_all()
    # สร้าง User ตัวอย่างหากยังไม่มีในระบบ
    if not User.query.filter_by(username='user01').first():
        hashed_pw = generate_password_hash('password123')
        new_user = User(username='user01', password=hashed_pw, is_admin=False)
        db.session.add(new_user)
        
    if not User.query.filter_by(username='admin01').first():
        hashed_admin_pw = generate_password_hash('admin123')
        admin_user = User(username='admin01', password=hashed_admin_pw, is_admin=True)
        db.session.add(admin_user)
        
    db.session.commit()

# --- Routes ---

@app.route('/')
def home():
    if 'username' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        
        return render_template('login.html', error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'username' not in session or session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/api/checkin', methods=['POST'])
def checkin_api():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'กรุณาเข้าสู่ระบบ'}), 401

    try:
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        image_file = request.files.get('image')

        if not latitude or not longitude or not image_file:
            return jsonify({'status': 'error', 'message': 'ข้อมูลไม่ครบถ้วน (ต้องมี พิกัด และรูปภาพ)'}), 400

        # จัดการบันทึกภาพ
        filename = secure_filename(image_file.filename)
        # ตกแต่งชื่อไฟล์ป้องกันซ้ำด้วยเวลา
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        image_file.save(file_path)

        # บันทึกลงฐานข้อมูล
        new_record = CheckInRecord(
            username=session['username'],
            latitude=float(latitude),
            longitude=float(longitude),
            image_filename=unique_filename
        )
        db.session.add(new_record)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'เช็คอินสำเร็จเรียบร้อย!'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    # ดึงรายการเช็คอินทั้งหมด เรียงลำดับจากล่าสุด
    records = CheckInRecord.query.order_by(CheckInRecord.timestamp.desc()).all()
    return render_template('admin.html', username=session['username'], records=records)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
