from flask import Flask
from flask_cors import CORS
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
import time
import socket
import requests  # برای گرفتن IP عمومی

# --- بلوپرینت‌ها ---
from routes.holoo import holoo_bp
from routes.main import main_bp
from routes.visitory_erfan import Holoo_bp, get_db_connection, sync_visitors
from routes.config_utils import load_db_config
from routes.table_initializer import setup_all_databases

# --- تنظیمات Flask ---
app = Flask(__name__)
app.secret_key = "mysecretkey"
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- پورت ---
FLASK_PORT = 5000
FLASK_HOST = '0.0.0.0'  # گوش دادن روی تمام اینترفیس‌ها

# --- همگام‌سازی بازاریاب‌ها ---
def schedule_sync_visitors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sync_visitors(cursor)
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("🔄 همگام‌سازی بازاریاب‌ها با موفقیت انجام شد.")
    except Exception as e:
        logging.error(f"❌ خطا در همگام‌سازی زمان‌بندی شده: {e}")

# --- زمان‌بندی ---
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(schedule_sync_visitors, "interval", minutes=1)
scheduler.start()

# --- اجرای setup اولیه پایگاه داده ---
setup_all_databases()

# --- ثبت بلوپرینت‌ها ---
app.register_blueprint(holoo_bp)
app.register_blueprint(main_bp)
app.register_blueprint(Holoo_bp, url_prefix="/HolooPage")

# --- گرفتن IP عمومی ---
def get_public_ip():
    try:
        return requests.get("https://api.ipify.org").text
    except:
        return None

# --- اجرای سرور با Waitress ---
def run_flask_server():
    logging.info(f"🚀 سرور Flask در حال راه‌اندازی روی پورت {FLASK_PORT}...")
    serve(app, host=FLASK_HOST, port=FLASK_PORT)

# --- نقطه شروع ---
if __name__ == "__main__":
    # نمایش IP‌ها قبل از اجرای سرور
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    public_ip = get_public_ip()

    logging.info("="*60)
    logging.info("✅ سرور Flask آماده اجرا!")
    logging.info(f"🌐 دسترسی محلی: http://{local_ip}:{FLASK_PORT}")
    if public_ip:
        logging.info(f"🌍 دسترسی اینترنتی (Public IP): http://{public_ip}:{FLASK_PORT}")
        logging.info("⚠️ برای دسترسی اینترنتی، پورت روی روتر فوروارد شود")
    else:
        logging.info("❌ امکان دریافت IP عمومی وجود ندارد.")
    logging.info("="*60)

    # اجرای سرور
    run_flask_server()
