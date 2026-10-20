import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Google Drive API Client Libraries
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'moc-checkin-secure-key-2025-token')

# ==========================================
# 1. การเชื่อมต่อฐานข้อมูล Supabase (PostgreSQL)
# ==========================================
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # ปรับแต่ง URL scheme ให้รองรับ SQLAlchemy v2+
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # โหมดรันจำลองออฟไลน์ในเครื่อง (Fallback to local SQLite)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checkin.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # จำกัดขนาดรูปถ่าย 16MB

db = SQLAlchemy(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==========================================
# 2. ฟังก์ชัน Google Drive API Service
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/drive.file']
GOOGLE_DRIVE_FOLDER_ID = os.environ.get('1C4VP75saXvlbs27-a0Dls-Z4zu9SCqLy', '')

def get_drive_service():    
    """สร้าง Client เชื่อมต่อ Google Drive API ผ่าน Service Account"""
    try:
        # 1. ตรวจสอบผ่านตัวแปรระบบบน Render (GOOGLE_CREDENTIALS)
        creds_json = os.environ.get({
  "type": "service_account",
  "project_id": "demomoc",
  "private_key_id": "6fc1f1cbdb4b16b5e094264144226907414b2c4b",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDcyv4nRlSawsDo\nj4aDL5PoyEiDAtlBZHnz+Tg9RBrK5xm3xQUeEU+6vfJVzkXkW0Jyi0UsJpU2BqdH\nj7Rwdz99hcgLUzjnTvOCvlv0lsgJdJLc0piY0SJYQCwlIVsiGTqm3hn2BqTEkc46\nCoOxTBG4xkbkZhrZ9LY8eKOack+03AHH+Lbx86neiJsEQ2Fvxhq5JXenADGcQbv/\nqWQkbvOkWkW0C0+fKF8I71fKb/4qOSItk0PBhorq2j9nqyo5JGIW/fn/O1mit70m\ntQEhfp6FSuTCCyWm2cgamBcTzrTAmNpV8sO1BQ6y503wV2HMGA7TtUtkDW1dFsql\nd2yepe+zAgMBAAECggEARiRm4WtCbXf5eOg/v2VaA9W804IQKuoUpCFEcJI2QMdy\nMCNzIL43Kgg1+HRzV7x2O5VrAD+xn1w1wFIy7Je1n9bkWlSx+ynlyl9XLzjHi9lw\n3p44xDOMSaT5YUJbhVWmgGSGstYheiEn9uBoPecAqkazNtQJK7zGOCfLMcGm+Llk\nzxIQhXxxtv7yQlO+CB6HRrKfIvaxfUlmtJZbnuZhLIQe+P/AMd4hoeJKYwf5GJIr\npQ5bcq+YP98ujVxiSZafKlxD8+XBx8AD6KwIhpiEsaIc+FAKXCYkNYpbkwA/8WrD\nHcAK6XALRfNLByy9WctJDS52ViHnoW3zKv6ssA+KAQKBgQD5B19lQ0KEaTgKeSeg\ncr3LwV8Uymc/rE0TVBHaTyxWoWrUzMskx7jmASw9ZpJkqCJiQuHZ7ln4uMIDXuHf\nzVaemQDQ0xFRt6zuTc+fBPvY7gevh/xrFYGZbGrkIOLnVYMaf1L2HviwIMG/GGPM\nqzEw/Kkt0bgPI6iScR3r893eQQKBgQDi+UWpufFwXx/0tugCKID2hVnQ0QROmWgL\nHHR30QF+VaVggu6bQUyCbJbVqh6q9iu/lP2kPfaUqVKJS33+wK7qlLf6/Lr0OekS\ng+heY+mS9GGrbx00fcNl3j8WjaeMecHvJYZd+Hov+DhVg7P7WY2pdDHLxa2U4BgK\n8a7wLn348wKBgQC3pyRHPc80b5SQxMDgpz4pojZI0uxKHPvKoVl5MqJ0UR7ESTQX\nr+NAXOUPczHLYePZq5F8czePIlKSwcq6jmivFg9v8fj31wmFxYS0taw2U3T/kr4p\nCvdE+pvqGga8rGe/ht7b/ANTgRThpU8UhbwFcJAj5mJjZ9zOAvYaKQMbAQKBgClc\nscQ/XW9T9nfbCSaziOTj4j06ieVk8V/s/JCFJxeFthCDa8YhPTcbYNVpHhObrtdH\n6H0QyanHvYHFnx1YsceP+IMloVA2aXH1Vdg1rvAX1uCt7A2PyZb7zFVo1Rq1aZES\nLo1bZbDuNB3pVVg9tqIlyZlP2dUijV8ZMf8VCeHfAoGBAJfPyjbxLNqt9nEgSxnD\nEzZyVgwniUY+a6F/i92JVEwn/3HxFEXa/+6fIRyR8kDqf75PxarkLiQaSPcK9s/M\n3C0tK58iAryXsZ9Kk+dclrtTnqDdqyyupYl47CA0vts+B9XxL0RNFZGArb5N1lTk\nrRbx8FF6rct3sGelPA47MhYw\n-----END PRIVATE KEY-----\n",
  "client_email": "drive-uploader@demomoc.iam.gserviceaccount.com",
  "client_id": "109427306539459144985",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/drive-uploader%40demomoc.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
})
        if creds_json:
            info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)

        # 2. ตรวจสอบผ่านไฟล์ Local (google-credentials.json)
        local_creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'google-credentials.json')
        if os.path.exists(local_creds_path):
            creds = service_account.Credentials.from_service_account_file(local_creds_path, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)

        return None
    except Exception as e:
        print(f"[Drive API Init Error] {str(e)}")
        return None

def upload_file_to_drive(file_path, file_name):
    """ส่งไฟล์ภาพขึ้น Drive และเปิดสิทธิ์ Public Reader เพื่อให้ดึงรูปไปแสดงผลได้"""
    try:
        service = get_drive_service()
        if not service:
            print("[Drive API Error] Google Credentials not found.")
            return None

        file_metadata = {
            'name': file_name,
            'parents': [GOOGLE_DRIVE_FOLDER_ID] if GOOGLE_DRIVE_FOLDER_ID else []
        }
        media = MediaFileUpload(file_path, mimetype='image/jpeg', resumable=True)

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = uploaded.get('id')

        # เปิดสิทธิ์ Reader แบบ Public ให้กับรูปภาพเพื่อให้แสดงใน Dashboard ได้
        try:
            service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception as perm_err:
            print(f"[Drive Permission Notice] {str(perm_err)}")

        return file_id
    except Exception as e:
        print(f"[Drive Upload Error] {str(e)}")
        return None

# ==========================================
# 3. โครงสร้างตารางฐานข้อมูล (ORM Models)
# ==========================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class CheckInRecord(db.Model):
    __tablename__ = 'checkin_records'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    drive_file_id = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# สร้างตารางและข้อมูลผู้ใช้งานเริ่มต้นอัตโนมัติ
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='user01').first():
        db.session.add(User(username='user01', password=generate_password_hash('password123'), is_admin=False))
    if not User.query.filter_by(username='admin01').first():
        db.session.add(User(username='admin01', password=generate_password_hash('admin123'), is_admin=True))
    db.session.commit()

# ==========================================
# 4. ส่วนจัดเส้นทาง (Routes)
# ==========================================
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('admin_dashboard') if session.get('is_admin') else url_for('index'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('index'))

        return render_template('login.html', error="ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")
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
        return jsonify({'status': 'error', 'message': 'กรุณาเข้าสู่ระบบก่อนทำรายการ'}), 401

    temp_path = None
    try:
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        image_file = request.files.get('image')

        if not latitude or not longitude or not image_file:
            return jsonify({'status': 'error', 'message': 'ข้อมูลไม่ครบถ้วน (ต้องการพิกัดและรูปถ่าย)'}), 400

        # บันทึกไฟล์พักชั่วคราวบนเซิร์ฟเวอร์
        filename = secure_filename(image_file.filename)
        unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{session['username']}_{filename}"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        image_file.save(temp_path)

        # อัปโหลดตรงเข้า Google Drive
        drive_file_id = upload_file_to_drive(temp_path, unique_name)
        if not drive_file_id:
            return jsonify({'status': 'error', 'message': 'การอัปโหลดรูปภาพเข้า Google Drive ล้มเหลว โปรดตรวจสอบการตั้งค่า'}), 500

        # บันทึกข้อมูลและ Drive File ID ลงฐานข้อมูล Supabase PostgreSQL
        new_record = CheckInRecord(
            username=session['username'],
            latitude=float(latitude),
            longitude=float(longitude),
            drive_file_id=drive_file_id
        )
        db.session.add(new_record)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'เช็คอินและบันทึกรูปภาพเข้าสู่ระบบสำเร็จ!'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'ระบบขัดข้อง: {str(e)}'}), 500
    finally:
        # เคลียร์ไฟล์ชั่วคราวเสมอเพื่อไม่ให้เปลือง Disk Space
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    records = CheckInRecord.query.order_by(CheckInRecord.timestamp.desc()).all()
    return render_template('admin.html', username=session['username'], records=records)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)