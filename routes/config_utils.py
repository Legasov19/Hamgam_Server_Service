import json
import pyodbc
CONFIG_FILE = 'db_config.json'

def save_db_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def load_db_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def get_article_connection():
    """اتصال به دیتابیس مقاله‌ها از فایل تنظیمات"""  
    db_info = load_db_config()
    if not db_info:
        raise Exception("تنظیمات دیتابیس ذخیره نشده است!")
    conn = pyodbc.connect(
        f"DRIVER={db_info['driver']};"
        f"SERVER={db_info['server']};"
        f"DATABASE={db_info['database']};"
        f"UID={db_info['username']};"
        f"PWD={db_info['password']};"
        f"TrustServerCertificate=yes;"
    )
    return conn
def get_main_db_connection1():
    """اتصال به دیتابیس اصلی پروژه"""
    return pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=185.192.114.114;'
        'DATABASE=VisitoryMainDb;'
        'UID=Visitory_maindb_2;'
        'PWD=467y?u3kX;'
        'TrustServerCertificate=yes;'
    )
def get_second_db_connection1():
    """اتصال به دیتابیس دوم پروژه"""
    return pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=185.192.114.114;'
        'DATABASE=webcom_main;'
        'UID=webcom_main1;'
        'PWD=f3C3!65gr;'
        'TrustServerCertificate=yes;'
    )