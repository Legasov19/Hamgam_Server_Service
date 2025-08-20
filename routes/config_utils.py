import json
import pyodbc
from flask import (
    Flask,
    g,
)
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
    db_info = getattr(g, "db_config", None) or load_db_config()
    if not db_info:
        raise Exception("تنظیمات دیتابیس ذخیره نشده است!")

    driver = db_info.get("driver")
    server = db_info.get("server")
    database = db_info.get("database")
    username = db_info.get("username")
    password = db_info.get("password")
    trust_cert = db_info.get("trust_server_certificate", "yes")

    encrypt_option = "Encrypt=yes;" if "ODBC Driver 18" in driver else ""

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"{encrypt_option}"
        f"TrustServerCertificate={trust_cert};"
    )

    return pyodbc.connect(conn_str)






def get_main_db_connection1():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=185.192.114.114;"
        "DATABASE=VisitoryMainDb;"
        "UID=Visitory_maindb_2;"
        "PWD=467y?u3kX;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )


def get_second_db_connection1():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=185.192.114.114;"
        "DATABASE=webcom_main;"
        "UID=webcom_main1;"
        "PWD=f3C3!65gr;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
