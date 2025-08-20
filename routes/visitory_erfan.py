from flask import Flask, request, jsonify
import datetime
from sqlite3 import Cursor
import traceback
from flask import (
    Flask,
    g,
    request,
    Blueprint,
    flash,
    logging,
    make_response,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    send_file,
    Response,
)
from functools import wraps

from numpy import conj
import pyodbc
import json
import os
import math
from datetime import datetime, timedelta
import logging
import re
import uuid
import random
import urllib.parse
from PIL import Image
from io import BytesIO
import requests
from bs4 import BeautifulSoup
import sys
from flask_cors import CORS
import urllib.parse
from flask_cors import cross_origin
import mimetypes


app = Flask(__name__)
Holoo_bp = Blueprint("Holoo", __name__, url_prefix="/HolooPage")

CONFIG_FILE = "db_config.json"


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

CONFIG_FILE = "db_config.json"
user_databases = {}  # apikey → config map (موقت داخل حافظه)

# -----------------------------
# دکوراتور بررسی API Key


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        apikey = request.headers.get("x-api-key", "").strip()
        if not apikey or apikey not in user_databases:
            return jsonify({"error": "API Key نامعتبر"}), 403

        g.db_config = user_databases[apikey]
        return f(*args, **kwargs)
    return decorated

# -----------------------------


def save_db_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def load_db_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# -----------------------------


def get_db_connection():
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

# -----------------------------


def get_main_db_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=185.192.114.114;"
        "DATABASE=VisitoryMainDb;"
        "UID=Visitory_maindb_2;"
        "PWD=467y?u3kX;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )


def get_second_db_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=185.192.114.114;"
        "DATABASE=webcom_main;"
        "UID=webcom_main1;"
        "PWD=f3C3!65gr;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

# -----------------------------
# لاگین و گرفتن apikey


@Holoo_bp.route("/get-user-conn", methods=["POST"])
def get_user_conn_info():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn1 = conn2 = None
    try:
        # مرحله 1: گرفتن ApiKey
        conn1 = get_main_db_connection()
        cursor1 = conn1.cursor()
        cursor1.execute(
            """
            SELECT ApiKey, TypeApplication
            FROM dbo.ConnectionMainDb
            WHERE UserName = ? AND Password = ?
            """,
            (username, password),
        )
        row1 = cursor1.fetchone()
        cursor1.close()

        if not row1:
            return jsonify({"error": "Invalid username or password"}), 404

        api_key, type_application = row1

        # مرحله 2: گرفتن Connection String اصلی
        conn2 = get_second_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute(
            """
            SELECT ConnectionStringLocal, FldConnection
            FROM dbo.TblMain
            WHERE ApiKey = ?
            """,
            (api_key,),
        )
        row2 = cursor2.fetchone()
        cursor2.close()

        if not row2:
            return jsonify({"error": "No matching record found"}), 404

        full_conn_string, fld_connection = row2

        # مرحله 3: استخراج provider connection string
        ef_match = re.search(
            r"provider connection string='([^']+)'", full_conn_string, re.IGNORECASE)
        actual_conn_string = ef_match.group(
            1) if ef_match else full_conn_string

        conn_parts = dict(re.findall(
            r"(?i)(data source|server|initial catalog|database|user id|uid|password|pwd|integrated security)\s*=\s*([^;]+)",
            actual_conn_string
        ))

        conn_info = {
            "server": conn_parts.get("data source") or conn_parts.get("server"),
            "database": conn_parts.get("initial catalog") or conn_parts.get("database"),
            "username": conn_parts.get("user id") or conn_parts.get("uid"),
            "password": conn_parts.get("password") or conn_parts.get("pwd"),
            "integrated_security": conn_parts.get("integrated security", "").lower() == "true",
        }

        ip_match = re.search(
            r"(\d{1,3}(?:\.\d{1,3}){3})", fld_connection or "")
        ip_address = ip_match.group(1) if ip_match else None

        result = {
            "driver": "ODBC Driver 18 for SQL Server",
            "server": conn_info["server"],
            "database": conn_info["database"],
            "username": conn_info.get("username"),
            "password": conn_info.get("password"),
            "apikey": api_key,
            "type_application": type_application,
            "ip_address": ip_address,
            "use_integrated_security": conn_info["integrated_security"]
        }

        # ذخیره روی فایل
        save_db_config(result)
        # ذخیره روی حافظه
        user_databases[api_key] = result

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn1:
            conn1.close()
        if conn2:
            conn2.close()

# -----------------------------


def add_image_column_with_default(
    default_image_url="https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp",
):
    conn = get_db_connection()
    cursor = conn.cursor()
    # 1. بررسی وجود ستون Image
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Image'
    """
    )
    column_exists = cursor.fetchone()
    # 2. اگر ستون وجود نداشت، آن را اضافه کن
    if not column_exists:
        cursor.execute(
            """
            ALTER TABLE dbo.ARTICLE
            ADD Image NVARCHAR(255)
        """
        )
        conn.commit()
        print("ستون Image اضافه شد.")
    # 3. مقداردهی پیش‌فرض برای همه سطرها
    cursor.execute(
        """
        UPDATE dbo.ARTICLE
        SET Image = ?
        WHERE Image IS NULL
    """,
        default_image_url,
    )
    conn.commit()
    print("مقداردهی ستون Image با آدرس اینترنتی انجام شد.")
    cursor.close()
    conn.close()


@Holoo_bp.route("/", methods=["GET"])
def Holoo_page():
    return render_template("Holoo.html")


@Holoo_bp.route("/save_db_config", methods=["POST"])
def save_db_config_route():
    db_info = {
        "server": request.form["server"],
        "database": request.form["database"],
        "username": request.form["username"],
        "password": request.form["password"],
        "driver": request.form["driver"],
    }
    save_db_config(db_info)
    return redirect(url_for("Holoo.Holoo_page"))


class ReportService:
    def __init__(self):
        self.conn = get_db_connection()

    def close(self):
        if self.conn:
            self.conn.close()

    def get_report(self, code, take, start_date=None, end_date=None):
        try:
            if not isinstance(take, int) or take <= 0 or take > 1000:
                take = 10

            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            if isinstance(end_date, str):
                end_date = datetime.strptime(
                    end_date, "%Y-%m-%d") + timedelta(days=1)

            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT Moien_Code_Bed, Tafzili_Code_Bed FROM CUSTOMER WHERE C_Code=?",
                    (code,),
                )
                res = cursor.fetchone()
                if not res:
                    return []

                moin_code, tafzili_code = res
                if not moin_code:
                    return []

                date_filter = ""
                params = []
                if start_date and end_date:
                    date_filter = " AND sa.Sanad_Date >= ? AND sa.Sanad_Date < ? "
                    params.extend([start_date, end_date])
                elif start_date:
                    date_filter = " AND sa.Sanad_Date >= ? "
                    params.append(start_date)
                elif end_date:
                    date_filter = " AND sa.Sanad_Date < ? "
                    params.append(end_date)

                if tafzili_code and tafzili_code.strip() != "":
                    query = f"""
                    SELECT TOP {take} s.Sanad_Code, s.Bed, s.Bes, s.Comment_Line, s.Type_Line, sa.Sanad_Date
                    FROM SND_LIST s
                    INNER JOIN Sanad sa ON s.Sanad_Code = sa.Sanad_Code
                    WHERE s.Moien_Code=? AND s.Tafzili_Code=? {date_filter}
                    ORDER BY sa.Sanad_Date DESC
                    """
                    params = [moin_code, tafzili_code] + params
                else:
                    query = f"""
                    SELECT TOP {take} s.Sanad_Code, s.Bed, s.Bes, s.Comment_Line, s.Type_Line, sa.Sanad_Date
                    FROM SND_LIST s
                    INNER JOIN Sanad sa ON s.Sanad_Code = sa.Sanad_Code
                    WHERE s.Moien_Code=? AND (s.Tafzili_Code IS NULL OR s.Tafzili_Code='') {date_filter}
                    ORDER BY sa.Sanad_Date DESC
                    """
                    params = [moin_code] + params

                cursor.execute(query, params)
                rows = cursor.fetchall()
                if not rows:
                    return []

            rows = rows[::-1]
            result_list = []
            sum_mande = 0

            with self.conn.cursor() as cursor_web:
                for r in rows:
                    sanad_code, bed, bes, comment, type_line, sanad_date = r
                    bed = bed or 0
                    bes = bes or 0

                    cursor_web.execute(
                        "SELECT Fac_Code, C_Code, Fac_Date, Fac_Type FROM FACTURE WHERE Sanad_Code = ?",
                        (sanad_code,),
                    )
                    facture_row = cursor_web.fetchone()

                    fac_code = facture_row[0] if facture_row else None
                    fact_c_code = facture_row[1] if facture_row else None
                    fact_date = facture_row[2] if facture_row else None
                    fac_type = facture_row[3] if facture_row else None

                    cust_mobile = None
                    cust_name = None
                    if fact_c_code:
                        cursor_web.execute(
                            "SELECT C_Mobile, C_Name FROM CUSTOMER WHERE C_Code = ?",
                            (fact_c_code,),
                        )
                        cust_info = cursor_web.fetchone()
                        if cust_info:
                            cust_mobile, cust_name = cust_info

                    order_details = []
                    if fac_code:
                        cursor_web.execute(
                            """
                            SELECT f.Tedad, f.Sel_Price, f.PricePay, a.A_Name, f.Few_Article, f.Price_BS, f.VahedCode
                            FROM FACTART f
                            LEFT JOIN Article a ON f.A_Code = a.A_Code
                            WHERE f.Fac_Code = ?
                            """,
                            (fac_code,),
                        )
                        art_rows = cursor_web.fetchall()
                        for art in art_rows:
                            order_details.append(
                                {
                                    "Kala_Name": art[3] or "",
                                    "Few_Article": art[4] or 0,
                                    "Price_BS": art[5] or 0,
                                    "VahedCode": art[6] or "",
                                }
                            )

                    mande_satri = bed - bes
                    sum_mande += mande_satri

                    result_list.append(
                        {
                            "Sanad_Code": sanad_code,
                            "DateTime": (
                                fact_date.strftime("%Y-%m-%d %H:%M:%S")
                                if fact_date
                                else None
                            ),
                            "Bed": bed,
                            "Bes": bes,
                            "Title": comment or "",
                            "MANDE": sum_mande,
                            "Type_Line": type_line,
                            "Fac_Code": fac_code,
                            "Fac_Type": fac_type,
                            "Cust_Code": fact_c_code,
                            "Cust_Mobile": cust_mobile,
                            "Cust_Name": cust_name,
                            "Order_Details": order_details,
                            "Sanad_Date": (
                                sanad_date.strftime(
                                    "%Y-%m-%d") if sanad_date else None
                            ),
                        }
                    )

            return result_list

        except Exception as e:
            logging.error(f"Error in get_report: {e}")
            logging.error(traceback.format_exc())
            return []


def send_moien_by_mobile(mobile, take, start_date=None, end_date=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT C_Code FROM CUSTOMER WHERE C_Mobile=?", (mobile,))
        user = cursor.fetchone()
        if not user:
            return None

        c_code = user[0]
        report_service = ReportService()
        result = report_service.get_report(
            c_code, take, start_date=start_date, end_date=end_date
        )
        report_service.close()
        cursor.close()
        conn.close()
        return result

    except Exception as e:
        logging.error(f"Error in send_moien_by_mobile: {e}")
        logging.error(traceback.format_exc())
        return None


@Holoo_bp.route("/send_all_moien", methods=["POST"])
@require_api_key
def send_all_moien():
    try:
        data = request.get_json(force=True)
        take = data.get("take", 10)

        if not isinstance(take, int) or take <= 0 or take > 1000:
            take = 10

        # دریافت کد مشتری‌ها که Moien_Code_Bed دارند
        report_service = ReportService()  # اتصال توسط کلاس مدیریت می‌شود

        with report_service.conn.cursor() as cursor:
            cursor.execute(
                "SELECT C_Code FROM CUSTOMER WHERE Moien_Code_Bed IS NOT NULL AND Moien_Code_Bed <> ''"
            )
            customer_codes = cursor.fetchall()

        if not customer_codes:
            report_service.close()
            return jsonify({"message": "هیچ مشتری با کد معین پیدا نشد"}), 404

        all_reports = []

        for (code,) in customer_codes:
            partial_report = report_service.get_report(code, take)
            if partial_report:
                all_reports.extend(partial_report)

        report_service.close()

        if not all_reports:
            return jsonify({"message": "هیچ گزارشی یافت نشد"}), 404

        # مرتب‌سازی بر اساس DateTime نزولی
        sorted_reports = sorted(
            all_reports, key=lambda x: x.get("DateTime") or "", reverse=True
        )

        final_report = sorted_reports[:take]

        return jsonify({
            "message": f"{len(final_report)} گزارش معین آخر دریافت شد",
            "data": final_report,
        }), 200

    except Exception as e:
        logging.error(f"Error in send_all_moien: {e}")
        logging.error(traceback.format_exc())
        return jsonify({
            "message": "خطا در دریافت گزارش معین کلی",
            "error": str(e),
        }), 500


@Holoo_bp.route("/send_moien_single_mobile", methods=["POST"])
@require_api_key
def send_moien_single_mobile():
    try:
        data = request.get_json(force=True)
        mobile = data.get("mobile")
        take = data.get("take", 10)
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not mobile:
            return jsonify({"message": "شماره موبایل ارسال نشده است"}), 400

        if not isinstance(take, int) or take <= 0 or take > 1000:
            take = 10

        def validate_date(date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                return None

        start_date_obj = validate_date(start_date) if start_date else None
        end_date_obj = validate_date(end_date) if end_date else None

        if (start_date and not start_date_obj) or (end_date and not end_date_obj):
            return (
                jsonify({"message": "فرمت تاریخ‌ها باید به صورت yyyy-mm-dd باشد"}),
                400,
            )

        result = send_moien_by_mobile(
            mobile, take, start_date=start_date_obj, end_date=end_date_obj
        )

        if result:
            return (
                jsonify(
                    {
                        "message": "گزارش معین برای شماره موبایل دریافت شد",
                        "data": result,
                    }
                ),
                200,
            )
        else:
            return jsonify({"message": "هیچ گزارشی برای این شماره پیدا نشد"}), 404

    except Exception as e:
        logging.error(f"Error in send_moien_single_mobile: {e}")
        logging.error(traceback.format_exc())
        return (
            jsonify(
                {
                    "message": "خطا در دریافت گزارش برای شماره موبایل",
                    "error": str(e),
                }
            ),
            500,
        )


def make_image_url(article_code):
    base_url = request.host_url.rstrip("/")
    # اجبار به https
    base_url = base_url.replace("http://", "https://", 1)

    if article_code:
        encoded_code = urllib.parse.quote(article_code)
        url = f"{base_url}/get_image_by_code?code={encoded_code}"
    else:
        url = f"{base_url}/get_image_by_code?default=1"

    print("IMAGE URL:", url)
    return url


@Holoo_bp.route("/Get_Holoo_Articles", methods=["GET", "POST"])
@require_api_key
def get_holoo_articles():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # دریافت داده‌ها
        if request.method == "POST":
            data = request.get_json(force=True) or {}
            page_raw = data.get("pageid") or data.get("page", "1")
        else:
            data = request.args or {}
            page_raw = data.get("page", "1")

        # تبدیل صفحه
        try:
            page = int(page_raw)
        except (ValueError, TypeError):
            if isinstance(page_raw, str) and page_raw.lower() == "all":
                page = "all"
            else:
                page = 1

        per_page = int(data.get("per_page", 10)) if page != "all" else None
        only_all = page == "all"

        visitor_id = data.get("visitor_id")
        try:
            price_type = int(data.get("price_type", 1)) if not only_all else 1
        except Exception:
            price_type = 1

        # دریافت قیمت‌های سفارشی فقط در POST و JSON
        custom_prices = {}
        if request.method == "POST" and request.is_json:
            cp = data.get("custom_prices", {})
            if isinstance(cp, dict):
                custom_prices = cp

        # اعتبارسنجی اولیه
        if request.method == "GET" and not only_all and not visitor_id:
            return jsonify({"error": "visitor_id الزامی است."}), 400

        if not only_all and not (1 <= price_type <= 10):
            return jsonify({"error": "price_type باید بین 1 تا 10 باشد."}), 400

        # تنظیمات دسترسی اولیه
        show_all_prices = True
        show_end_buy_price = False
        can_enter_fee = False
        show_gifts = False

        # دریافت تنظیمات ویزیتور
        if not only_all and visitor_id:
            cursor.execute(
                """
                SELECT WSetTip, ShowEndBuyPrice, WEnterFee, WSetEshan
                FROM TblSetting_Visitori
                WHERE FldC_Visitor = ?
                """,
                (visitor_id,),
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "کد ویزیتور نامعتبر است."}), 404

            show_all_prices = bool(row[0])
            show_end_buy_price = bool(row[1])
            can_enter_fee = bool(row[2])
            show_gifts = bool(row[3])

            if price_type > 1 and not show_all_prices:
                return (
                    jsonify(
                        {"error": "دسترسی مشاهده قیمت تیپ برای این ویزیتور وجود ندارد."}
                    ),
                    403,
                )

        # دریافت کالاها
        if only_all:
            cursor.execute(
                """
                SELECT a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist, a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,a.Include_Tax,a.Levy,
                       a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5, a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                       a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton, p.PicturePath
                FROM article a
                LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                WHERE a.A_Code IS NOT NULL AND a.A_Name IS NOT NULL AND a.Sel_Price IS NOT NULL AND a.Sel_Price > 0 AND a.IsActive = 1
                ORDER BY a.A_Name ASC
                """
            )
        else:
            offset = (page - 1) * per_page
            cursor.execute(
                """
                SELECT * FROM (
                    SELECT 
                        a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist, a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,a.Include_Tax,a.Levy,
                        a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5, a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                        a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton, p.PicturePath,
                        ROW_NUMBER() OVER (ORDER BY a.A_Name ASC) AS rn
                    FROM article a
                    LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                    WHERE a.A_Code IS NOT NULL AND a.A_Name IS NOT NULL AND a.Sel_Price IS NOT NULL AND a.Sel_Price > 0 AND a.IsActive = 1
                ) AS sub
                WHERE rn BETWEEN ? AND ?
                """,
                (offset + 1, offset + per_page),
            )

        articles = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

        # دریافت واحدها
        cursor.execute(
            "SELECT Unit_Code, Unit_Name, Unit_Few, Vahed_Vazn FROM UNIT")
        units_raw = cursor.fetchall()
        units = {str(row[0]): row[1] for row in units_raw}
        unit_fews = {str(row[0]): str(row[2]) for row in units_raw if row[2]}
        unit_weights = {str(row[0]): row[3] for row in units_raw if row[3]}

        # دریافت کدهای هدیه
        cursor.execute(
            "SELECT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL"
        )
        gifted_codes = {row[0] for row in cursor.fetchall()}

        article_list = []
        for row in articles:
            row_dict = dict(zip(columns, row))
            article_code = row_dict["A_Code"]
            price_column = "Sel_Price" if price_type == 1 else f"Sel_Price{price_type}"
            try:
                sel_price = float(row_dict.get(price_column) or 0)
            except Exception:
                sel_price = 0.0

            # قیمت سفارشی اگر وجود داشته باشد
            if (
                request.method == "POST"
                and can_enter_fee
                and article_code in custom_prices
            ):
                try:
                    sel_price = float(custom_prices[article_code])
                except Exception:
                    pass

            try:
                darsad_takhfif = float(row_dict.get("DarsadTakhfif") or 0)
            except Exception:
                darsad_takhfif = 0.0
            try:
                price_takhfif = float(row_dict.get("PriceTakhfif") or 0)
            except Exception:
                price_takhfif = 0.0

            takhfif_final = sel_price
            if darsad_takhfif > 0:
                takhfif_final -= sel_price * darsad_takhfif / 100
            elif price_takhfif > 0:
                takhfif_final -= price_takhfif

            vahed_code = str(row_dict.get("VahedCode"))
            vahed_name = units.get(vahed_code, "نامشخص")
            vahed_riz_name = units.get(unit_fews.get(vahed_code, ""), "نامشخص")
            vahed_weight = unit_weights.get(vahed_code, "نامشخص")
            image_url = make_image_url(article_code)

            try:
                exist = int(row_dict.get("Exist") or 0)
            except Exception:
                exist = 0

            try:
                max_val = float(row_dict.get("A_Max") or 0)
            except Exception:
                max_val = 0

            try:
                min_val = float(row_dict.get("A_Min") or 0)
            except Exception:
                min_val = 0

            try:
                karton = int(row_dict.get("Karton") or 0)
            except Exception:
                karton = 0

            article_data = {
                "FldC_Kala": article_code,
                "FldACode_C": row_dict.get("A_Code_C"),
                "FldN_Kala": row_dict.get("A_Name"),
                "FldFee": sel_price,
                "FldFeeBadAzTakhfif": takhfif_final,
                "FldMande": exist,
                "FldN_Vahed": vahed_name,
                "FldN_Vahed_Riz": vahed_riz_name,
                "FldVahedVazn": vahed_weight,
                "FldTozihat": row_dict.get("Attribute") or "",
                "FldMax": max_val,
                "FldMin": min_val,
                "FldTedadKarton": karton,
                "FldImage": image_url,
                "IsGifted": article_code in gifted_codes,
                "CanEnterFee": can_enter_fee,
                "TaxLevy": float(row_dict.get("Levy") or 0),
            }
            if row_dict.get("Include_Tax"):
                article_data["Tax"] = "محصول شامل مالیات می‌شود"

            if show_end_buy_price:
                try:
                    article_data["EndBuyPrice"] = float(
                        row_dict.get("EndBuy_Price") or 0
                    )
                except Exception:
                    article_data["EndBuyPrice"] = 0

            if show_all_prices:
                for i in range(2, 11):
                    try:
                        article_data[f"Sel_Price{i}"] = float(
                            row_dict.get(f"Sel_Price{i}") or 0
                        )
                    except Exception:
                        article_data[f"Sel_Price{i}"] = 0

            article_list.append(article_data)

        gift_list = []
        if show_gifts:
            cursor.execute(
                """
                SELECT Gift_ID, A_Code, A_Code_C, A_Name, Model, Buy_Price, Gift_Code, is_gift, Created_At,Quantity,Threshold
                FROM dbo.MyGift_WC
                WHERE is_gift = 1
                """
            )
            gifts = cursor.fetchall()
            gift_columns = [col[0] for col in cursor.description]

            for gift_row in gifts:
                gift_dict = dict(zip(gift_columns, gift_row))
                gift_list.append(gift_dict)

        total_count = None
        if not only_all:
            cursor.execute(
                """
                SELECT COUNT(*) FROM article
                WHERE A_Code IS NOT NULL AND A_Name IS NOT NULL AND Sel_Price IS NOT NULL AND Sel_Price > 0 AND IsActive = 1
                """
            )
            total_count = cursor.fetchone()[0]

        result = {
            "data": article_list,
            "total": total_count,
            "gifts": gift_list,
            "page": None if only_all else page,
            "per_page": None if only_all else per_page,
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def output_path(relative_path):
    """مسیر ذخیره‌سازی کنار فایل اجرایی یا مسیر اصلی پروژه"""
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# تابع دریافت URL عکس از گوگل (محدود به سایت digikala.com)
def fetch_image_url(name):
    query = urllib.parse.quote(f"{name} site:digikala.com")
    url = f"https://www.google.com/search?q={query}&tbm=isch"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Google image search failed with status: {response.status_code}"
        )
    soup = BeautifulSoup(response.text, "html.parser")
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src")
        if src and src.startswith("http"):
            return src
    return None


@Holoo_bp.route("/get_images_by_codes", methods=["POST", "OPTIONS"])
@require_api_key
@cross_origin()
def get_images_by_codes():
    if request.method == "OPTIONS":
        return "", 200

    data = request.get_json()
    if not data:
        return jsonify({"error": "درخواست فاقد داده‌ی JSON معتبر است"}), 400

    item_codes = data.get("item_codes", [])
    item_names_dict = data.get("item_names", {})
    item_names_only = data.get("item_names_only", [])
    save_codes = data.get("save_codes", [])
    force_refresh = data.get("force_refresh", False)

    results = []

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # پردازش item_names_only
            for item in item_names_only:
                code = item.get("code")
                name = item.get("name")
                try:
                    img_url = fetch_image_url(name)
                    results.append(
                        {
                            "code": code,
                            "name": name,
                            "image_url": img_url,
                            "saved_path": None,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "code": code,
                            "name": name,
                            "image_url": None,
                            "saved_path": None,
                            "error": str(e),
                        }
                    )

            # پردازش کدهای آیتم
            for code in item_codes:
                cursor.execute(
                    "SELECT A_Name FROM Article WHERE A_Code = ?", (code,))
                row = cursor.fetchone()

                # مقدار نام از ورودی یا دیتابیس
                name = item_names_dict.get(code)
                if not name:
                    if row and row[0]:
                        name = row[0]
                    else:
                        name = None

                if not name:
                    results.append(
                        {
                            "code": code,
                            "name": f"نام کالا برای کد {code} در دیتابیس موجود نیست",
                            "image_url": None,
                            "saved_path": None,
                        }
                    )
                    continue

                try:
                    img_url = fetch_image_url(name)
                    saved_path = None

                    if img_url and code in save_codes:
                        save_dir = output_path("static/item_images")
                        os.makedirs(save_dir, exist_ok=True)
                        save_path = os.path.join(save_dir, f"{code}.jpg")

                        if force_refresh or not os.path.exists(save_path):
                            response = requests.get(img_url)
                            if response.status_code == 200:
                                img_data = response.content
                                with Image.open(BytesIO(img_data)) as image:
                                    image = image.convert("RGB")
                                    image = image.resize((600, 400))
                                    image.save(
                                        save_path, format="JPEG", quality=95)
                            else:
                                raise Exception(
                                    f"دانلود تصویر با خطا مواجه شد: {response.status_code}"
                                )

                        saved_path = save_path.replace("\\", "/")

                    results.append(
                        {
                            "code": code,
                            "name": name,
                            "image_url": img_url,
                            "saved_path": saved_path,
                        }
                    )

                except Exception as e:
                    results.append(
                        {
                            "code": code,
                            "name": name,
                            "image_url": None,
                            "saved_path": None,
                            "error": str(e),
                        }
                    )

        return jsonify(results)

    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


def resource_path(relative_path):
    base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


logger = logging.getLogger(__name__)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


@Holoo_bp.route("/get_image_by_code")
@require_api_key
def get_image_by_code():
    import os
    from flask import send_file, redirect, request

    code = request.args.get("code")
    default_image_url = (
        "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
    )
    save_dir = os.path.abspath("static/item_images")

    if not code or not code.isalnum():
        print(f"Invalid or missing code: {code}")
        return redirect(default_image_url)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT PicturePath, image_src FROM [HLOPictures] WHERE Code = ?", (
                code,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            picture_path, image_src = row

            print(
                f"From DB - PicturePath: {picture_path}, Exists: {os.path.exists(picture_path)}"
            )

            if picture_path and os.path.exists(picture_path):
                # مسیر مطلق باشه، اگر نیست تبدیل کن
                abs_path = os.path.abspath(picture_path)
                print(f"Sending file: {abs_path}")
                return send_file(abs_path, mimetype="image/jpeg")

            if image_src and isinstance(image_src, (bytes, bytearray)):
                from io import BytesIO

                print("Sending image from image_src bytes")
                return send_file(BytesIO(image_src), mimetype="image/jpeg")

    except Exception as e:
        print(f"Error querying DB or sending file: {e}")

    # fallback: چک کردن فایل در فولدر static/item_images
    fallback_image_path = os.path.join(save_dir, f"{code}.jpg")
    print(
        f"Checking fallback image path: {fallback_image_path}, Exists: {os.path.exists(fallback_image_path)}"
    )
    if os.path.exists(fallback_image_path):
        return send_file(fallback_image_path, mimetype="image/jpeg")

    print("Redirecting to default image URL")
    return redirect(default_image_url)


@Holoo_bp.route("/update_article_price", methods=["POST"])
@require_api_key
def update_article_price():
    data = request.get_json()
    visitor_id = data.get("visitor_id")
    article_code = data.get("article_code")
    new_price = data.get("custom_price")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT WEnterFee FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
        (visitor_id,),
    )
    row = cursor.fetchone()

    if not row or str(row[0]).strip() != "1":
        return jsonify({"error": "شما مجاز به وارد کردن قیمت دستی نیستید"}), 403

    # مثال نمایشی: درج قیمت در جدول سفارش موقت یا سبد خرید
    cursor.execute(
        """
        UPDATE Cart SET CustomPrice = ?
        WHERE VisitorID = ? AND ArticleCode = ?
    """,
        (new_price, visitor_id, article_code),
    )
    conn.commit()

    return jsonify({"message": "قیمت جدید با موفقیت ثبت شد."}), 200


logger = logging.getLogger(__name__)

# مسیر پیش‌فرض پوشه عکس‌ها
BASE_IMAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "static", "item_images")
)

# آدرس عکس پیش‌فرض
DEFAULT_IMAGE_URL = (
    "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
)


@Holoo_bp.route("/get_image")
@require_api_key
def get_image():
    try:
        path = request.args.get("path")
        code = request.args.get("code")

        # اگر فولدر مقصد وجود ندارد، ایجاد شود
        if not os.path.exists(BASE_IMAGE_DIR):
            os.makedirs(BASE_IMAGE_DIR)

        # حالت 1: دریافت از طریق code
        if code:
            if not code.isalnum():
                return redirect(DEFAULT_IMAGE_URL)

            img_path = os.path.join(BASE_IMAGE_DIR, f"{code}.jpg")

            if os.path.exists(img_path):
                return send_file(img_path, mimetype="image/jpeg")
            else:
                logger.warning(f"Image not found for code: {code}")
                return redirect(DEFAULT_IMAGE_URL)

        # حالت 2: دریافت از طریق path (مثلاً: 0801002.jpg)
        if path:
            safe_path = (
                urllib.parse.unquote(path).replace(
                    "/", os.sep).replace("\\", os.sep)
            )
            full_path = os.path.abspath(
                os.path.join(BASE_IMAGE_DIR, safe_path))

            # جلوگیری از دسترسی به خارج از فولدر مجاز
            if not full_path.startswith(BASE_IMAGE_DIR):
                logger.warning(
                    f"Access to path outside allowed directory: {full_path}")
                return redirect(DEFAULT_IMAGE_URL)

            if os.path.exists(full_path):
                return send_file(full_path, mimetype="image/jpeg")
            else:
                logger.warning(f"Image not found for path: {full_path}")
                return redirect(DEFAULT_IMAGE_URL)

        # اگر هیچ ورودی نبود، فایل جدیدترین تصویر را نشان بده
        files = [
            os.path.join(BASE_IMAGE_DIR, f)
            for f in os.listdir(BASE_IMAGE_DIR)
            if os.path.isfile(os.path.join(BASE_IMAGE_DIR, f))
        ]
        if files:
            latest_file = max(files, key=os.path.getmtime)
            return send_file(latest_file, mimetype="image/jpeg")
        else:
            return redirect(DEFAULT_IMAGE_URL)

    except Exception as e:
        logger.error(f"❌ Error in get_image: {e}")
        return redirect(DEFAULT_IMAGE_URL)


# --- گرفتن اسم کالا از دیتابیس ---


@Holoo_bp.route("/Search_Holoo_Articles", methods=["GET"])
@require_api_key
def search_holoo_articles():

    def normalize_search_input(text):
        """Normalizes user input for consistent searching."""
        replacements = {
            "ی": "ي", "ئ": "ي", "ک": "ك", "ۀ": "ه", "ة": "ه",
            "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
            "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
            "‌": "", "ـ": "", "“": '"', "”": '"', "‘": "'", "’": "'",
            "٫": ".", "٬": ",", "(": "(", ")": ")"
        }
        for f, r in replacements.items():
            text = text.replace(f, r)
        return text.strip()

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        search_term = request.args.get("search", "").strip()
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        start_row = (page - 1) * per_page + 1
        end_row = page * per_page

        if not search_term:
            return jsonify({"error": "پارامتر جستجو ارسال نشده است"}), 400

        # Normalize user input (including converting 'ک' to 'ك')
        normalized_search_term = normalize_search_input(search_term)
        search_filter = f"%{normalized_search_term}%"

        # --- MODIFIED QUERY ---
        # Count query with REPLACE for consistent character matching
        count_query = """
            SELECT COUNT(*) FROM article 
            WHERE (
                REPLACE(A_Name, N'ک', N'ك') LIKE ? OR A_Code LIKE ?
            )
            AND A_Code IS NOT NULL AND A_Name IS NOT NULL 
            AND Sel_Price IS NOT NULL AND Sel_Price > 0 
            AND IsActive = 1
        """
        cursor.execute(count_query, (search_filter, search_filter))
        total_items = cursor.fetchone()[0]
        total_pages = math.ceil(
            total_items / per_page) if total_items > 0 else 0

        articles = []
        if total_items > 0:
            # --- MODIFIED QUERY ---
            # Data query with REPLACE for consistent character matching
            data_query = """
            WITH OrderedArticles AS (
                SELECT 
                    A_Code, A_Code_C, A_Name, Sel_Price, VahedCode, Exist, Attribute,
                    DarsadTakhfif, PriceTakhfif, Sel_Price2, Sel_Price3, Sel_Price4,
                    Sel_Price5, Sel_Price6, Sel_Price7, Sel_Price8, Sel_Price9, Sel_Price10,
                    Include_Tax, Levy, EndBuy_Price, A_Max, A_Min, Karton, PicturePath,
                    ROW_NUMBER() OVER (ORDER BY A_Name ASC) AS RowNum
                FROM article
                WHERE (
                    REPLACE(A_Name, N'ک', N'ك') LIKE ? OR A_Code LIKE ?
                )
                AND A_Code IS NOT NULL AND A_Name IS NOT NULL 
                AND Sel_Price IS NOT NULL AND Sel_Price > 0 
                AND IsActive = 1
            )
            SELECT * FROM OrderedArticles WHERE RowNum BETWEEN ? AND ?
            """
            cursor.execute(data_query, (search_filter,
                           search_filter, start_row, end_row))
            articles = cursor.fetchall()

        if not articles:
            return jsonify({
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "shown_this_page": 0,
                "total_pages": total_pages,
                "Articles": [],
                "message": "کالایی برای نمایش یافت نشد."
            })

        columns = [col[0] for col in cursor.description]

        # Fetch supporting data
        cursor.execute(
            "SELECT DISTINCT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL")
        gifted_codes = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT Unit_Code, Unit_Name FROM UNIT")
        units = {row[0]: row[1] for row in cursor.fetchall()}

        articles_list = []
        for row in articles:
            row_dict = dict(zip(columns, row))
            article_code = row_dict["A_Code"]

            sel_price = float(row_dict.get("Sel_Price") or 0)
            darsad_takhfif = float(row_dict.get("DarsadTakhfif") or 0)
            price_takhfif = float(row_dict.get("PriceTakhfif") or 0)

            if darsad_takhfif > 0:
                final_price = sel_price * (1 - darsad_takhfif / 100)
            elif price_takhfif > 0:
                final_price = sel_price - price_takhfif
            else:
                final_price = sel_price

            # --- CORRECTED FUNCTION CALL ---
            image_url = make_image_url(article_code)

            article_data = {
                "FldC_Kala": article_code,
                "FldACode_C": row_dict.get("A_Code_C"),
                "FldN_Kala": row_dict.get("A_Name"),
                "FldFee": sel_price,
                "FldMande": int(row_dict.get("Exist") or 0),
                "FldN_Vahed": units.get(row_dict.get("VahedCode"), "نامشخص"),
                "FldTozihat": row_dict.get("Attribute") or "",
                "FldFeeBadAzTakhfif": final_price,
                "Sel_Price2": float(row_dict.get("Sel_Price2") or 0),
                "Sel_Price3": float(row_dict.get("Sel_Price3") or 0),
                "Sel_Price4": float(row_dict.get("Sel_Price4") or 0),
                "Sel_Price5": float(row_dict.get("Sel_Price5") or 0),
                "Sel_Price6": float(row_dict.get("Sel_Price6") or 0),
                "Sel_Price7": float(row_dict.get("Sel_Price7") or 0),
                "Sel_Price8": float(row_dict.get("Sel_Price8") or 0),
                "Sel_Price9": float(row_dict.get("Sel_Price9") or 0),
                "Sel_Price10": float(row_dict.get("Sel_Price10") or 0),
                "EndBuyPrice": float(row_dict.get("EndBuy_Price") or 0),
                "FldMax": float(row_dict.get("A_Max") or 0),
                "FldMin": float(row_dict.get("A_Min") or 0),
                "FldTedadKarton": int(row_dict.get("Karton") or 0),
                "FldImage": image_url,
                "IsGifted": article_code in gifted_codes,
                "TaxLevy": float(row_dict.get("Levy") or 0),
                "Tax": "محصول شامل مالیات می‌شود" if row_dict.get("Include_Tax") else "محصول شامل مالیات نمی‌شود"
            }
            articles_list.append(article_data)

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "shown_this_page": len(articles_list),
            "total_pages": total_pages,
            "Articles": articles_list,
        })

    except Exception as e:
        # Log the full error for debugging
        # import traceback
        # print(traceback.format_exc())
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@Holoo_bp.route("/update_visitor", methods=["POST"])
@require_api_key
def update_visitor():
    def ensure_table_exists(cursor):
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT * FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'TblSetting_Visitori'
            )
            BEGIN
                CREATE TABLE TblSetting_Visitori (
                    FldC_Visitor NVARCHAR(50) PRIMARY KEY,
                    FldMob NVARCHAR(50),
                    FldN_Visitor NVARCHAR(100),
                    WDarsadSoud DECIMAL(10,2),
                    WMandeHesab DECIMAL(18,2),
                    FldVahedpool NVARCHAR(50),
                    FldP_ForooshBishAzMojoodi BIT,
                    FldS_Foroosh BIT,
                    FldGps BIT,
                    FldShowMande BIT,
                    FldNewMoshtari BIT,
                    FldSignature BIT,
                    FldShowBedehkaran BIT,
                    FldMarjooii BIT,
                    FldVoroodTozihKala BIT,
                    FldDoVahedi BIT,
                    FldTracker BIT,
                    FldTimeTrack NVARCHAR(50),
                    FldSabtGpsShakhs BIT,
                    FldShowGpsShakhs BIT,
                    FldAutoRecive BIT,
                    FldTimeRecive NVARCHAR(50),
                    FldNameForooshgah NVARCHAR(100),
                    FldTellForooshgah NVARCHAR(50),
                    FldAddressForooshgah NVARCHAR(200),
                    FldToken NVARCHAR(100),
                    FldKharidBiashAz NVARCHAR(50),
                    FldDarsadTakhfifRiali DECIMAL(10,2),
                    FldEtelaResani BIT,
                    FldZamanTahvil NVARCHAR(50),
                    WSetTip NVARCHAR(50),
                    WEnterFee NVARCHAR(50),
                    WIsModir BIT,
                    WSetEshan BIT,
                    WHideBMande BIT,
                    WShowMoiens BIT,
                    WMegaModir BIT,
                    WUseAnbarak BIT,
                    ShowEndBuyPrice BIT,
                    AddFactorComment NVARCHAR(200),
                    IsPos BIT,
                    FldStartWork NVARCHAR(50),
                    FldEndWork NVARCHAR(50),
                    ShowReport BIT
                )
            END
            """
        )

    try:
        data = request.get_json(silent=True) or {}
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_table_exists(cursor)

        # 🟡 نمایش همه یا یک بازاریاب خاص
        if (
            not data
            or data.get("list") is True
            or ("FldC_Visitor" in data and len(data) == 1)
        ):
            fld_code = data.get("FldC_Visitor")

            if fld_code:
                # فقط یک بازاریاب خاص
                cursor.execute(
                    "SELECT * FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
                    (fld_code,),
                )
            else:
                # نمایش همه بازاریاب‌ها
                cursor.execute("SELECT * FROM TblSetting_Visitori")

            columns = [col[0] for col in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return jsonify({"visitors": records})

        # 🟢 آپدیت دستی یک بازاریاب
        if "FldC_Visitor" in data:
            code = data["FldC_Visitor"]
            update_fields = {k: v for k,
                             v in data.items() if k != "FldC_Visitor"}

            if not update_fields:
                return jsonify({"error": "No fields provided to update."}), 400

            cursor.execute(
                "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?", (
                    code,)
            )
            if not cursor.fetchone():
                return jsonify({"error": f"Visitor with code '{code}' not found."}), 404

            cursor.execute(
                """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'TblSetting_Visitori'
                """
            )
            valid_columns = {row[0] for row in cursor.fetchall()}
            invalid_fields = [
                f for f in update_fields if f not in valid_columns]
            if invalid_fields:
                return (
                    jsonify(
                        {"error": f"Invalid fields: {', '.join(invalid_fields)}"}),
                    400,
                )

            set_clause = ", ".join(f"[{k}] = ?" for k in update_fields)
            values = list(update_fields.values()) + [code]
            cursor.execute(
                f"UPDATE TblSetting_Visitori SET {set_clause} WHERE FldC_Visitor = ?",
                values,
            )
            conn.commit()

            return jsonify(
                {
                    "message": "Visitor updated successfully.",
                    "FldC_Visitor": code,
                    "updated_fields": update_fields,
                }
            )

        # 🔁 سینک با جدول CUSTOMER
        cursor.execute(
            """
            SELECT C_Mobile, C_Name, C_Code, Vaseteh_Porsant
            FROM CUSTOMER
            WHERE C_Mobile IS NOT NULL AND C_Mobile != ''
              AND C_Name IS NOT NULL AND C_Name != ''
              AND C_Code IS NOT NULL AND C_Code != ''
              AND Vaseteh = 1 AND City_Code IS NOT NULL
            """
        )
        columns = [col[0] for col in cursor.description]
        customers = [dict(zip(columns, row)) for row in cursor.fetchall()]

        inserted, updated = 0, 0
        for customer in customers:
            code = customer["C_Code"]
            cursor.execute(
                "SELECT FldMob, FldN_Visitor, WDarsadSoud FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
                (code,),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE TblSetting_Visitori
                    SET FldMob = ?, 
                        FldN_Visitor = ?, 
                        WDarsadSoud = ?
                    WHERE FldC_Visitor = ?
                    """,
                    (
                        customer["C_Mobile"],
                        customer["C_Name"],
                        str(customer["Vaseteh_Porsant"] or 0),
                        code,
                    ),
                )
                updated += 1
            else:
                cursor.execute(
                    """
                    INSERT INTO TblSetting_Visitori (
                        FldC_Visitor, FldMob, FldN_Visitor, WDarsadSoud, WMandeHesab, FldVahedpool, FldEtelaResani, FldZamanTahvil
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code,
                        customer["C_Mobile"],
                        customer["C_Name"],
                        str(customer["Vaseteh_Porsant"] or 0),
                        0,
                        "ریال",
                        1,
                        "تحویل 24 ساعت پس از فاکتور",
                    ),
                )
                inserted += 1

        conn.commit()
        return jsonify(
            {
                "message": f"{updated} updated, {inserted} inserted into TblSetting_Visitori"
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/get_visitors", methods=["GET"])
@require_api_key
def get_visitors():
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        query = """
            SELECT 
                FldC_Visitor,
                FldMob,
                FldN_Visitor,
                FldTellForooshgah,
                FldNameForooshgah,
                WDarsadSoud,
                FldAddressForooshgah,
                FldVahedpool,
                FldEtelaResani,
                FldZamanTahvil
            FROM TblSetting_Visitori
        """

        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        visitors = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return jsonify(visitors)

    except Exception as e:
        import traceback

        logging.error(f"Error in get_visitors: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Internal Server Error"}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/get_customer_cities", methods=["GET"])
@require_api_key
def get_customer_cities():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # دریافت City_Codeهای منحصربه‌فرد از جدول CUSTOMER
        cursor.execute(
            "SELECT DISTINCT City_Code FROM CUSTOMER WHERE City_Code IS NOT NULL"
        )
        city_codes = [row[0] for row in cursor.fetchall()]

        if not city_codes:
            return jsonify({"cities": []})

        # دریافت اطلاعات کامل مناطق از جدول CITY
        placeholders = ",".join("?" for _ in city_codes)
        cursor.execute(
            f"""
            SELECT City_Code, Name, In_Out, Top_Code, Choice, City_Etebar
            FROM CITY
            WHERE City_Code IN ({placeholders})
            """,
            city_codes,
        )
        cities = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

        return jsonify({"cities": cities})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()

def get_visitors_from_customer():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT C_Mobile, C_Name, C_Code, C_Address, C_Tel, C_AliasName, Vaseteh_Porsant
        FROM CUSTOMER 
        WHERE C_Mobile IS NOT NULL AND C_Mobile != ''
          AND C_Name IS NOT NULL AND C_Name != ''
          AND C_Code IS NOT NULL AND C_Code != ''
          AND Vaseteh = 1
    """
    cursor.execute(query)

    columns = [column[0] for column in cursor.description]
    customers = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return customers


def insert_visitors_into_tblsetting(customers):
    conn = get_db_connection()
    cursor = conn.cursor()

    for customer in customers:
        # اول بررسی کنیم این بازاریاب قبلا ثبت شده یا نه
        cursor.execute(
            "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
            (customer["C_Code"],)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(
                """
                INSERT INTO TblSetting_Visitori (
                    FldC_Visitor, FldMob, FldN_Visitor, WDarsadSoud,
                    FldVahedpool, FldNameForooshgah, FldTellForooshgah,
                    FldAddressForooshgah, FldEtelaResani, FldZamanTahvil
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer["C_Code"],          # FldC_Visitor
                    customer["C_Mobile"],        # FldMob
                    customer["C_Name"],          # FldN_Visitor
                    customer["Vaseteh_Porsant"] or 0,  # WDarsadSoud
                    "ریال",                      # FldVahedpool
                    customer["C_AliasName"] or "",  # FldNameForooshgah
                    customer["C_Tel"] or "",        # FldTellForooshgah
                    customer["C_Address"] or "",    # FldAddressForooshgah
                    "ساعت کار فروشگاه از 7 صبح لغایت 19 می‌باشد",  # FldEtelaResani
                    "تحویل 24 ساعت پس از تاریخ فاکتور می‌باشد",   # FldZamanTahvil
                ),
            )

    conn.commit()
    cursor.close()
    conn.close()


@Holoo_bp.route("/send_visitors", methods=["POST"])
def send_visitors():
    try:
        customers = get_visitors_from_customer()
        insert_visitors_into_tblsetting(customers)
        return jsonify({"message": f"{len(customers)} بازاریاب ذخیره شد."})
    except Exception as e:
        logging.error(f"Error in send_visitors: {e}")
        return jsonify({"error": str(e)}), 500

@Holoo_bp.route("/get_customers_by_city", methods=["POST"])
@require_api_key
def get_customers_by_city():
    try:
        data = request.get_json(silent=True) or {}
        city_code = data.get("City_Code")
        page = int(data.get("page", 1))
        per_page = int(data.get("per_page", 10))

        if not city_code:
            return jsonify({"error": "City_Code is required"}), 400

        offset = (page - 1) * per_page
        start_row = offset + 1
        end_row = offset + per_page

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی وجود شهر
        cursor.execute(
            "SELECT Name FROM CITY WHERE City_Code = ?", (city_code,))
        city = cursor.fetchone()
        if not city:
            return jsonify({"error": f"No city found with code '{city_code}'"}), 404

        city_name = city[0]

        # تعداد کل مشتریان با موبایل معتبر
        cursor.execute(
            """
            SELECT COUNT(*) FROM CUSTOMER 
            WHERE City_Code = ? 
              AND C_Mobile IS NOT NULL AND C_Mobile != ''
            """,
            (city_code,)
        )
        total_customers = cursor.fetchone()[0]

        # دریافت مشتریان با موبایل معتبر و با استفاده از ROW_NUMBER
        cursor.execute(
            """
            SELECT C_Code, C_Name, C_Mobile FROM (
                SELECT C_Code, C_Name, C_Mobile,
                       ROW_NUMBER() OVER (ORDER BY C_Name) AS RowNum
                FROM CUSTOMER
                WHERE City_Code = ?
                  AND C_Mobile IS NOT NULL AND C_Mobile != ''
            ) AS RowConstrainedResult
            WHERE RowNum BETWEEN ? AND ?
            """,
            (city_code, start_row, end_row),
        )
        customers = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

        total_pages = (total_customers + per_page - 1) // per_page

        return jsonify(
            {
                "City_Code": city_code,
                "City_Name": city_name,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_customers": total_customers,
                    "total_pages": total_pages,
                },
                "customers": customers,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


def ensure_customer_visitor_log_table_exists(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        IF OBJECT_ID(N'dbo.CustomerVisitorLog', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.CustomerVisitorLog (
                Log_ID INT IDENTITY(1,1) PRIMARY KEY,
                C_Code NVARCHAR(50),
                C_Name NVARCHAR(200),
                Visitor_Code NVARCHAR(50),
                Created_At DATETIME DEFAULT GETDATE()
            )
        END
    """
    )
    conn.commit()


@Holoo_bp.route("/send_customers_Visitory", methods=["GET"])
@require_api_key
def send_customers():
    conn = get_db_connection()
    cursor = conn.cursor()

    def normalize_arabic(text):
        if not isinstance(text, str):
            return ""
        return (
            text.replace("ي", "ی")
            .replace("ك", "ک")
            .replace("ة", "ه")
            .replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ؤ", "و")
            .replace("ئ", "ی")
            .replace("ٱ", "ا")
            .replace("ۀ", "ه")
            .replace("ء", "")
            .replace("ّ", "")
            .replace("ٰ", "")
            .replace(" ", "")
            .replace("‌", "")
            .strip()
        )

    try:
        search_term = request.args.get("search", "").strip()
        visitor_code = request.args.get("visitor_code", "").strip()
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
        offset = (page - 1) * page_size

        cursor.execute(
            "SELECT WIsModir FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
            (visitor_code,),
        )
        result = cursor.fetchone()
        is_modir = result and result[0] == 1

        params = []
        where_clauses = [
            "c.C_Mobile IS NOT NULL AND c.C_Mobile != ''",
            "c.C_Name IS NOT NULL AND c.C_Name != ''",
            "c.C_Code IS NOT NULL AND c.C_Code != ''"
        ]

        if not is_modir and visitor_code:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM CUSTOMER_VISITOR cv WHERE cv.C_Code = c.C_Code AND cv.V_Code = ?)"
            )
            params.append(visitor_code)

        if search_term:
            search_norm = normalize_arabic(search_term)
            normalized_expr = (
                "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(c.C_Name, ' ', ''), "
                "N'ي', N'ی'), N'ك', N'ک'), N'ة', N'ه'), N'أ', N'ا'), N'إ', N'ا'), N'آ', N'ا'), "
                "N'ؤ', N'و'), N'ئ', N'ی'), N'ٱ', N'ا'), N'ۀ', N'ه'), N'ء', N''), N'ّ', N''), N'ٰ', N'')"
            )
            where_clauses.append(f"{normalized_expr} LIKE ?")
            params.append(f"%{search_norm}%")

        where_sql = " AND ".join(where_clauses)

        query = f"""
        WITH CTE AS (
            SELECT
                c.C_Code,
                c.C_Mobile,
                c.C_Name,
                c.C_Address,
                c.C_Tel,
                c.C_Code_C,
                c.Etebar,
                c.City_Code,
                city.Name AS City_Name,
                m.Mandeh,
                ROW_NUMBER() OVER (
                    PARTITION BY REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(c.C_Name, ' ', ''), N'ي', N'ی'), N'ك', N'ک'), N'ة', N'ه'), N'أ', N'ا'), N'إ', N'ا'), N'آ', N'ا'), N'ؤ', N'و'), N'ئ', N'ی'), N'ٱ', N'ا'), N'ۀ', N'ه'), N'ء', N''), N'ّ', N''), N'ٰ', N'') 
                    ORDER BY c.C_Code
                ) AS rn
            FROM CUSTOMER c
            LEFT JOIN CITY city ON city.City_Code = c.City_Code
            LEFT JOIN SARFASL m ON m.Common = c.C_Code
            WHERE {where_sql}
        )
        SELECT *
        FROM CTE
        WHERE rn > ? AND rn <= ?
        ORDER BY C_Code
        """

        params.extend([offset, offset + page_size])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        # Count query
        count_query = f"""
        SELECT COUNT(*) FROM (
            SELECT
                ROW_NUMBER() OVER (
                    PARTITION BY REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(c.C_Name, ' ', ''), N'ي', N'ی'), N'ك', N'ک'), N'ة', N'ه'), N'أ', N'ا'), N'إ', N'ا'), N'آ', N'ا'), N'ؤ', N'و'), N'ئ', N'ی'), N'ٱ', N'ا'), N'ۀ', N'ه'), N'ء', N''), N'ّ', N''), N'ٰ', N'') 
                    ORDER BY c.C_Code
                ) AS rn
            FROM CUSTOMER c
            WHERE {where_sql}
        ) AS sub
        WHERE rn = 1
        """

        # برای شمارش پارامترها به جز دو عدد مربوط به offset و limit است
        cursor.execute(count_query, params[:-2])
        total_count = cursor.fetchone()[0]

        def build_customer_dict(row):
            row_dict = dict(zip(columns, row))
            mandeh = row_dict["Mandeh"]
            vaziat = "بد حساب" if mandeh is not None and mandeh < 0 else "خوش حساب"
            return {
                "FldN_City": row_dict["City_Name"] or "",
                "FldC_Ashkhas": row_dict["C_Code"],
                "FldC_Ashkhas_C": row_dict["C_Code_C"] or "0",
                "FldAddress": row_dict["C_Address"] or "",
                "FldMob": row_dict["C_Mobile"],
                "FldTell": row_dict["C_Tel"] or "",
                "FldEtebar": str(row_dict["Etebar"] or "0"),
                "FldN_Ashkhas": row_dict["C_Name"],
                "FldC_City": str(row_dict["City_Code"] or ""),
                "FldMandeHesab": str(mandeh if mandeh is not None else "0"),
                "FldVaziat": vaziat,
                "FldTakhfifVizhe": "0",
                "FldC_Visitor": visitor_code,
                "FldTipFee": "0",
                "FldLat": "0",
                "FldLon": "0",
            }

        return jsonify({
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "customers": [build_customer_dict(row) for row in rows],
        })

    except Exception as e:
        import logging
        logging.exception("Error in send_customers")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@Holoo_bp.route("/assign_customer_to_visitor", methods=["POST"])
@require_api_key
def assign_customer_to_visitor():
    try:
        data = request.get_json(silent=True) or {}
        customer_code = data.get("C_Code")
        visitor_code = data.get("V_Code")

        if not customer_code or not visitor_code:
            return jsonify({"error": "C_Code and V_Code are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی وجود مشتری
        cursor.execute(
            "SELECT 1 FROM CUSTOMER WHERE C_Code = ?", (customer_code,))
        if not cursor.fetchone():
            return jsonify({"error": "Customer not found"}), 404

        # بررسی وجود ویزیتور
        cursor.execute(
            "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?", (
                visitor_code,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "Visitor not found"}), 404

        # بررسی وجود این ترکیب خاص
        cursor.execute(
            "SELECT 1 FROM CUSTOMER_VISITOR WHERE C_Code = ? AND V_Code = ?",
            (customer_code, visitor_code),
        )
        if cursor.fetchone():
            return (
                jsonify(
                    {"message": "Customer is already assigned to this visitor."}),
                200,
            )

        # ثبت جدید - چون اجازه چند ویزیتور برای هر مشتری داریم
        cursor.execute(
            "INSERT INTO CUSTOMER_VISITOR (C_Code, V_Code) VALUES (?, ?)",
            (customer_code, visitor_code),
        )

        conn.commit()
        return jsonify({"message": "Customer assigned to visitor successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/unassign_customer_from_visitor", methods=["POST"])
@require_api_key
def unassign_customer_from_visitor():
    try:
        data = request.get_json(silent=True) or {}
        customer_code = data.get("C_Code")
        visitor_code = data.get("V_Code")

        if not customer_code or not visitor_code:
            return jsonify({"error": "C_Code and V_Code are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1 FROM CUSTOMER_VISITOR
            WHERE C_Code = ? AND V_Code = ?
        """,
            (customer_code, visitor_code),
        )

        if not cursor.fetchone():
            return (
                jsonify(
                    {"error": "This customer is not assigned to this visitor."}),
                404,
            )

        # حذف ارتباط
        cursor.execute(
            """
            DELETE FROM CUSTOMER_VISITOR
            WHERE C_Code = ? AND V_Code = ?
        """,
            (customer_code, visitor_code),
        )

        conn.commit()
        return (
            jsonify({"message": "Customer unassigned from visitor successfully."}),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/get_customers_by_visitor", methods=["POST"])
@require_api_key
def get_customers_by_visitor():
    try:
        data = request.get_json(silent=True) or {}
        visitor_code = data.get("V_Code")

        if not visitor_code:
            return jsonify({"error": "V_Code is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی وجود ویزیتور
        cursor.execute(
            "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?", (
                visitor_code,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "Visitor not found"}), 404

        # دریافت اطلاعات مشتری‌ها
        cursor.execute(
            """
            SELECT 
                C.C_Code,
                C.C_Name,
                C.C_Mobile,
                C.C_Tel,
                C.C_Address,
                C.C_AliasName,
                C.Economic_Code,
                C.C_Code_C,
                C.Etebar,
                C.City_Code,
                CT.Name AS City_Name,
                M.Mandeh
            FROM CUSTOMER_VISITOR CV
            JOIN CUSTOMER C ON CV.C_Code = C.C_Code
            LEFT JOIN CITY CT ON CT.City_Code = C.City_Code
            LEFT JOIN W_Calc_Mandeh_Customer M ON M.C_Code = C.C_Code
            WHERE CV.V_Code = ?
            """,
            (visitor_code,),
        )

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

        def build_customer_dict(row):
            row_dict = dict(zip(columns, row))

            # فیلتر شرطی: اگر هر کدام از این 3 مقدار نبود، رد کن
            if (
                not row_dict["C_Code"]
                or not row_dict["C_Name"]
                or not row_dict["C_Mobile"]
            ):
                return None

            mandeh = row_dict["Mandeh"]
            vaziat = "بد حساب" if mandeh is not None and mandeh < 0 else "خوش حساب"

            return {
                "FldN_City": row_dict["City_Name"] or "",
                "FldC_Ashkhas": row_dict["C_Code"],
                "FldC_Ashkhas_C": row_dict["C_Code_C"] or "0",
                "FldAddress": row_dict["C_Address"] or "",
                "FldMob": row_dict["C_Mobile"],
                "FldTell": row_dict["C_Tel"] or "",
                "FldEtebar": str(row_dict["Etebar"] or "0"),
                "FldN_Ashkhas": row_dict["C_Name"],
                "FldC_City": str(row_dict["City_Code"] or ""),
                "FldMandeHesab": str(mandeh if mandeh is not None else "0"),
                "FldVaziat": vaziat,
                "FldTakhfifVizhe": "0",
                "FldC_Visitor": visitor_code,
                "FldTipFee": "0",
                "FldLat": "0",
                "FldLon": "0",
            }

        customers = []
        for row in rows:
            customer = build_customer_dict(row)
            if customer:
                customers.append(customer)

        return jsonify({"V_Code": visitor_code, "customers": customers}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/visitor_login", methods=["POST"])
@require_api_key
def visitor_login():
    try:
        data = request.get_json()
        mobile = data.get("mobile", "").strip()

        if not mobile:
            return jsonify({"error": "Mobile number is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # ساخت ستون FldToken اگر وجود نداشت
        cursor.execute(
            """
            IF COL_LENGTH('TblSetting_Visitori', 'FldToken') IS NULL
            BEGIN
                ALTER TABLE TblSetting_Visitori ADD FldToken NVARCHAR(255)
            END
        """
        )
        conn.commit()

        # جستجوی ویزیتور
        cursor.execute(
            """
            SELECT 
                FldC_Visitor, FldMob, FldN_Visitor, WDarsadSoud, WMandeHesab,
                FldVahedpool, FldP_ForooshBishAzMojoodi, FldS_Foroosh, FldGps, 
                FldShowMande, FldNewMoshtari, FldSignature, FldShowBedehkaran,
                FldMarjooii, FldVoroodTozihKala, FldDoVahedi, FldTracker, FldTimeTrack,
                FldSabtGpsShakhs, FldShowGpsShakhs, FldAutoRecive, FldTimeRecive,
                FldNameForooshgah, FldTellForooshgah, FldAddressForooshgah, FldToken,
                FldKharidBiashAz, FldDarsadTakhfifRiali, FldEtelaResani, FldZamanTahvil,
                WSetTip, WEnterFee, WIsModir, WSetEshan, WHideBMande, WShowMoiens,
                WMegaModir, WUseAnbarak, ShowEndBuyPrice, AddFactorComment, IsPos,
                FldStartWork, FldEndWork, ShowReport
            FROM TblSetting_Visitori
            WHERE FldMob = ?
        """,
            (mobile,),
        )

        visitor = cursor.fetchone()

        if not visitor:
            return jsonify({"error": "Visitor not found"}), 404

        # اگر توکن خالی بود → ساخت و ذخیره آن
        token = visitor.FldToken
        if not token or str(token).strip() == "":
            token = str(uuid.uuid4())
            cursor.execute(
                "UPDATE TblSetting_Visitori SET FldToken = ? WHERE FldMob = ?",
                (token, mobile),
            )
            conn.commit()

        # ساخت دیکشنری از نتیجه
        columns = [column[0] for column in cursor.description]
        result = dict(zip(columns, visitor))
        result["FldToken"] = token  # اطمینان از وجود مقدار

        return jsonify({"visitor": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/get_visitors_by_customer", methods=["POST"])
@require_api_key
def get_visitors_by_customer():
    try:
        data = request.get_json(silent=True) or {}
        customer_code = data.get("C_Code")

        if not customer_code:
            return jsonify({"error": "C_Code is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی وجود مشتری
        cursor.execute(
            "SELECT 1 FROM CUSTOMER WHERE C_Code = ?", (customer_code,))
        if not cursor.fetchone():
            return jsonify({"error": "Customer not found"}), 404

        # دریافت لیست بازاریاب‌هایی که به این مشتری اختصاص داده شدن
        cursor.execute(
            """
            SELECT 
                V.FldC_Visitor AS V_Code,
                V.FldN_Visitor AS Visitor_Name
            FROM CUSTOMER_VISITOR CV
            JOIN TblSetting_Visitori V ON CV.V_Code = V.FldC_Visitor
            WHERE CV.C_Code = ?
        """,
            (customer_code,),
        )

        visitors = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

        return jsonify({"C_Code": customer_code, "visitors": visitors}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/GroupsKala", methods=["GET"])
@require_api_key
def get_categories_with_subcategories():
    conn = get_db_connection()
    cursor = conn.cursor()

    if cursor is None:
        return jsonify({"error": "Database connection is not available."}), 500

    cursor.execute("SELECT M_groupcode, M_groupname FROM M_GROUP")
    main_categories = cursor.fetchall()
    categories_with_subcategories = []

    for main_category in main_categories:
        M_groupcode, M_groupname = main_category
        sub_categories_list = []

        cursor.execute(
            "SELECT S_groupcode, S_groupname FROM S_GROUP WHERE M_groupcode=?",
            (M_groupcode,),
        )
        sub_categories_query = cursor.fetchall()

        for sub_category in sub_categories_query:
            S_groupcode, S_groupname = sub_category
            sub_categories_list.append(
                {
                    "S_groupcode": S_groupcode,
                    "S_groupname": S_groupname,
                }
            )

        categories_with_subcategories.append(
            {
                "M_groupcode": M_groupcode,
                "M_groupname": M_groupname,
                "sub_categories": sub_categories_list,
            }
        )

    return jsonify(categories_with_subcategories)


@Holoo_bp.route("/register", methods=["POST"])
@require_api_key
def add_customer():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if cursor is None:
            return jsonify({"error": "Database connection is not available."}), 500

        # بررسی و افزودن ستون 'webcom' اگر وجود نداشت (SQL Server)
        cursor.execute(
            """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'CUSTOMER' AND COLUMN_NAME = 'webcom'
        """
        )
        column_exists = cursor.fetchone()
        if not column_exists:
            cursor.execute("ALTER TABLE CUSTOMER ADD webcom INT DEFAULT 0")
            conn.commit()

        data = request.get_json()
        phone_number = data.get("phoneNumber")
        full_name = data.get("fullName")
        address = data.get("address")
        national_code = data.get("nationalCode")
        region = data.get("region")  # Cust_Ostan
        city = data.get("city")  # Cust_City
        visitor_code = data.get("visitor_code")

        if not phone_number or not full_name or not visitor_code:
            return (
                jsonify(
                    {"error": "phoneNumber، fullName و visitor_code الزامی هستند"}),
                400,
            )

        cursor.execute(
            "SELECT FldNewMoshtari FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
            (visitor_code,),
        )
        visitor_setting = cursor.fetchone()
        if not visitor_setting:
            return jsonify({"error": "کد ویزیتور یافت نشد"}), 403
        if visitor_setting[0] != 1:
            return jsonify({"error": "شما مجاز به ثبت مشتری جدید نیستید"}), 403

        cursor.execute(
            "SELECT * FROM CUSTOMER WHERE C_Mobile = ? OR C_Name = ?",
            (phone_number, full_name),
        )
        existing_customer = cursor.fetchone()
        if existing_customer:
            return (
                jsonify(
                    {"message": "مشتری با این شماره یا نام قبلاً ثبت شده است."}),
                400,
            )

        cursor.execute("SELECT MAX(C_Code) FROM CUSTOMER")
        last_c_code = cursor.fetchone()[0]
        new_c_code = (
            str(int(last_c_code) + 1).zfill(len(last_c_code))
            if last_c_code
            else "00001"
        )

        creation_date = datetime.now()

        cursor.execute(
            """
            INSERT INTO CUSTOMER (
                C_Mobile, C_Name, C_Address, Creation_Date, C_Code, C_Code_C,
                National_Code, Cust_Ostan, Cust_City, webcom
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                phone_number,
                full_name,
                address,
                creation_date,
                new_c_code,
                new_c_code,
                national_code,
                region,
                city,
                1,  # مقدار webcom
            ),
        )

        conn.commit()
        return jsonify({"message": "مشتری با موفقیت ثبت شد", "C_Code": new_c_code}), 201

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@Holoo_bp.route("/ArticleByGroups", methods=["POST"])
@require_api_key
def get_articles_by_groups():
    conn = None
    try:
        data = request.get_json()
        M_groupcode = data.get("M_groupcode")
        S_groupcode = data.get("S_groupcode")

        if not M_groupcode and not S_groupcode:
            return (
                jsonify(
                    {"error": "حداقل یکی از M_groupcode یا S_groupcode باید ارسال شود"}
                ),
                400,
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        where_clause = "WHERE IsActive = 1"
        params = []

        # بررسی گروه اصلی
        if M_groupcode:
            cursor.execute(
                "SELECT 1 FROM M_GROUP WHERE M_groupcode = ?", (M_groupcode,)
            )
            if not cursor.fetchone():
                return jsonify({"error": "M_groupcode not found"}), 404
            where_clause += " AND SUBSTRING(A_Code, 1, 2) = ?"
            params.append(M_groupcode)

        # بررسی گروه فرعی
        if S_groupcode:
            cursor.execute(
                "SELECT 1 FROM S_GROUP WHERE S_groupcode = ?", (S_groupcode,)
            )
            if not cursor.fetchone():
                return jsonify({"error": "S_groupcode not found"}), 404
            where_clause += " AND SUBSTRING(A_Code, 3, 2) = ?"
            params.append(S_groupcode)

        # کوئری برای گرفتن مقالات
        query = f"""
            SELECT
                A_Code,
                A_Code_C,
                A_Name,
                Sel_Price,
                VahedCode,
                Exist,
                Karton,
                Attribute,
                DarsadTakhfif,
                PriceTakhfif,
                EndBuy_Price,
                A_Max,
                A_Min,
                Image
            FROM Article
            {where_clause}
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # گرفتن واحدها
        cursor.execute("SELECT Unit_Code, Unit_Name FROM UNIT")
        units = {row[0]: row[1] for row in cursor.fetchall()}

        # گرفتن کدهای هدیه
        cursor.execute(
            "SELECT DISTINCT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL"
        )
        gift_codes = {row[0] for row in cursor.fetchall()}

        articles = []
        for row in rows:
            (
                code,
                code_c,
                name,
                sel_price,
                vahed_code,
                exist,
                karton,
                attribute,
                d_takhfif,
                p_takhfif,
                end_buy,
                a_max,
                a_min,
                image,
            ) = row

            try:
                sel_price = float(sel_price or 0)
                d_takhfif = float(d_takhfif or 0)
                p_takhfif = float(p_takhfif or 0)
            except:
                sel_price, d_takhfif, p_takhfif = 0, 0, 0

            if d_takhfif > 0:
                final_price = sel_price - ((sel_price * d_takhfif) / 100)
            elif p_takhfif > 0:
                final_price = sel_price - p_takhfif
            else:
                final_price = sel_price

            articles.append(
                {
                    "FldC_Kala": code,
                    "FldACode_C": code_c,
                    "FldN_Kala": name,
                    "FldFee": sel_price,
                    "FldFeeBadAzTakhfif": final_price,
                    "FldN_Vahed": units.get(vahed_code, "نامشخص"),
                    "FldMande": exist or 0,
                    "FldTedadKarton": karton or 0,
                    "FldTozihat": attribute or "",
                    "EndBuyPrice": float(end_buy or 0),
                    "FldMax": float(a_max or 0),
                    "FldMin": float(a_min or 0),
                    "FldImage": image or "",
                    "IsGifted": code in gift_codes,
                }
            )

        return jsonify({"total": len(articles), "Articles": articles})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()


def ensure_webcom_column_exists():
    conn = None  # 🔒 برای جلوگیری از UnboundLocalError
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'RQTITLE' AND COLUMN_NAME = 'WEBCOM'
        """
        )
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE RQTITLE ADD WEBCOM BIT")
            conn.commit()
    except Exception as e:
        print("خطا در بررسی یا افزودن ستون WEBCOM:", e)
    finally:
        if conn:  # ✅ فقط اگر تعریف شده بود، بسته شود
            conn.close()


# اتصال به دیتابی


# دریافت کد مشتری از روی شماره موبایل
def get_customer_code(order):
    if not order["FldMobile"] or order["FldMobile"] == "0":
        return "error"

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT C_Code FROM CUSTOMER WHERE C_Mobile = ?", order["FldMobile"]
        )
        customer = cursor.fetchone()
        return customer.C_Code if customer else None

    except pyodbc.Error as e:
        logging.error("خطا در get_customer_code:")
        logging.error(str(e))
        logging.error(traceback.format_exc())
        return None

    finally:
        if conn:
            conn.close()


def ensure_visitor_column_exists():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'RQTITLE' AND COLUMN_NAME = 'Visitor_Code'
            )
            BEGIN
                ALTER TABLE RQTITLE ADD Visitor_Code NVARCHAR(50) NULL
            END
        """
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def fetch_order_details_by_date_range(date_from, date_to, visitor_code=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            t.RqIndex, t.RqType, t.R_CusCode, t.R_Date, t.T_Date, t.SumPrice, t.Visitor_Code,
            d.RqIndex AS DetailRqIndex, d.RqType AS DetailRqType, 
            d.R_ArCode, d.R_ArName, d.R_Few, d.R_Cost
        FROM RQTITLE t
        LEFT JOIN RQDETAIL d ON t.RqIndex = d.RqIndex
        WHERE t.WEBCOM = 1
    """

    params = []

    # اگر تاریخ all نبود، شرط تاریخ رو اضافه کن
    if date_from.lower() != "all" and date_to.lower() != "all":
        query += " AND CONVERT(DATE, t.R_Date, 120) BETWEEN ? AND ?"
        params.extend([date_from, date_to])

    if visitor_code:
        query += " AND t.Visitor_Code = ?"
        params.append(visitor_code)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


@Holoo_bp.route("/get_order_details", methods=["POST"])
@require_api_key
def get_order_details():
    data = request.get_json()
    R_Date_From = str(data.get("R_Date_From") or "").strip()
    R_Date_To = str(data.get("R_Date_To") or "").strip()
    visitor_code = str(data.get("Visitor_Code") or "").strip()

    if not R_Date_From or not R_Date_To:
        return jsonify({"error": "R_Date_From and R_Date_To are required"}), 400

    try:
        rows = fetch_order_details_by_date_range(
            R_Date_From, R_Date_To, visitor_code)
        orders = {}

        for row in rows:
            rq_index = row["RqIndex"]

            if rq_index not in orders:
                orders[rq_index] = {
                    "RQTITLE": {
                        "RqIndex": row["RqIndex"],
                        "RqType": row["RqType"],
                        "R_CusCode": row["R_CusCode"],
                        "R_Date": row["R_Date"],
                        "T_Date": row["T_Date"],
                        "SumPrice": row["SumPrice"],
                        "Visitor_Code": row["Visitor_Code"],
                    },
                    "RQDETAIL": [],
                }

            if row.get("R_ArCode"):
                orders[rq_index]["RQDETAIL"].append(
                    {
                        "RqIndex": row["DetailRqIndex"],
                        "RqType": row["DetailRqType"],
                        "R_ArCode": row["R_ArCode"],
                        "R_ArName": row["R_ArName"],
                        "R_Few": row["R_Few"],
                        "R_Cost": row["R_Cost"],
                    }
                )

        return jsonify({"Orders": list(orders.values())}), 200

    except Exception as e:
        logging.error(f"get_order_details error: {str(e)}")
        return jsonify({"error": str(e)}), 500


def fetch_best_selling_data(R_Date):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if R_Date.lower() == "all":
            query = """
                SELECT d.R_ArCode, d.R_ArName, d.R_Few
                FROM RQDETAIL d
                INNER JOIN RQTITLE t ON d.RqIndex = t.RqIndex2
                WHERE d.R_Few > 0 AND t.WEBCOM = 1
            """
            params = ()
        else:
            query = """
                SELECT d.R_ArCode, d.R_ArName, d.R_Few
                FROM RQDETAIL d
                INNER JOIN RQTITLE t ON d.RqIndex = t.RqIndex2
                WHERE CONVERT(DATE, t.R_Date, 120) = ? AND d.R_Few > 0 AND t.WEBCOM = 1
            """
            params = (R_Date,)

        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@Holoo_bp.route("/get_best_selling_articles", methods=["POST"])
@require_api_key
def get_best_selling_articles():
    data = request.get_json()
    R_Date = str(data.get("R_Date") or "").strip()

    if not R_Date:
        return jsonify({"error": "R_Date is required"}), 400

    try:
        rows = fetch_best_selling_data(R_Date)

        sales_map = {}
        for row in rows:
            code = row["R_ArCode"]
            name = row["R_ArName"]
            count = row["R_Few"] or 0

            if code:
                if code not in sales_map:
                    sales_map[code] = {
                        "R_ArCode": code,
                        "R_ArName": name,
                        "TotalCount": 0,
                    }
                sales_map[code]["TotalCount"] += count

        sorted_items = sorted(
            sales_map.values(), key=lambda x: x["TotalCount"], reverse=True
        )
        return jsonify({"BestSelling": sorted_items}), 200

    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@Holoo_bp.route("/facture/Moein", methods=["GET"])
@require_api_key
def get_facture_summary_by_ccode():
    c_code = request.args.get("C_Code")
    page = int(request.args.get("page", 1))  # پیش‌فرض: صفحه 1
    size = int(request.args.get("size", 5))  # پیش‌فرض: 5 مورد در هر صفحه
    # باید به فرمت 'YYYY-MM-DD' باشه
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")  # باید به فرمت 'YYYY-MM-DD' باشه

    if not c_code:
        return jsonify({"error": "پارامتر C_Code الزامی است"}), 400

    offset = (page - 1) * size

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # اگر start_date یا end_date برابر 'All' یا None بود، فیلتر تاریخ لحاظ نشود
        use_date_filter = (
            start_date
            and start_date.lower() != "all"
            and end_date
            and end_date.lower() != "all"
        )

        if use_date_filter:
            query = """
                SELECT Fac_Code, Fac_Type, Fac_Code_C, C_Code, Fac_Date, Fac_Time,
                       Sum_Price, Sum_Few
                FROM Facture
                WHERE C_Code = ?
                  AND Fac_Date BETWEEN ? AND ?
                ORDER BY Fac_Date DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            params = (c_code, start_date, end_date, offset, size)
        else:
            # بدون فیلتر تاریخ، همه رکوردها
            query = """
                SELECT Fac_Code, Fac_Type, Fac_Code_C, C_Code, Fac_Date, Fac_Time,
                       Sum_Price, Sum_Few
                FROM Facture
                WHERE C_Code = ?
                ORDER BY Fac_Date DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            params = (c_code, offset, size)

        cursor.execute(query, params)
        facture_rows = cursor.fetchall()

        if not facture_rows:
            cursor.close()
            conn.close()
            return (
                jsonify(
                    {
                        "message": "هیچ فاکتوری برای این مشتری یافت نشد.",
                        "page": page,
                        "size": size,
                        "factors": [],
                    }
                ),
                200,
            )

        result = []
        for row in facture_rows:
            (
                fac_code,
                fac_type,
                fac_code_c,
                c_code_value,
                fac_date,
                fac_time,
                sum_price,
                sum_few,
            ) = row

            cursor.execute(
                """
                SELECT 
                    Fac_Type, A_Code, A_Index,
                    Few_Article, Few_Article2,
                    Price_BS
                FROM FactArt 
                WHERE Fac_Code = ?
                """,
                (fac_code,),
            )

            all_details = cursor.fetchall()
            filtered_details = [
                dict(
                    zip(
                        [
                            "Fac_Type",
                            "A_Code",
                            "A_Index",
                            "Few_Article",
                            "Few_Article2",
                            "Price_BS",
                        ],
                        r,
                    )
                )
                for r in all_details
                if r[0] == "F"
            ]

            result.append(
                {
                    "Fac_Code": fac_code,
                    "Fac_Type": fac_type,
                    "Fac_Code_C": fac_code_c,
                    "C_Code": c_code_value,
                    "Fac_Date": str(fac_date),
                    "Fac_Time": str(fac_time),
                    "Sum_Price": sum_price,
                    "Sum_Few": sum_few,
                    "Details": filtered_details,
                }
            )

        cursor.close()
        conn.close()

        return jsonify({"page": page, "size": size, "factors": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@Holoo_bp.route("/SearchArticleByCodeOrName", methods=["POST"])
@require_api_key
def get_article_by_code_or_name():
    conn = None
    try:
        data = request.get_json()
        A_code_or_name = data.get("A_code_r_name")

        if not A_code_or_name:
            return jsonify({"error": "A_codeo_r_name is required"}), 400

        is_code = A_code_or_name.isdigit()
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_code:
            A_code = A_code_or_name
            M_groupcode = A_code[:2]
            S_groupcode = A_code[2:4]

            cursor.execute(
                "SELECT M_groupcode, M_groupname FROM M_Group WHERE M_groupcode = ?",
                M_groupcode,
            )
            m_group = cursor.fetchone()

            cursor.execute(
                "SELECT S_groupcode, S_groupname FROM S_GROUP WHERE S_groupcode = ?",
                S_groupcode,
            )
            s_group = cursor.fetchone()

            if not m_group or not s_group:
                return jsonify({"error": "M_groupcode or S_groupcode not found"}), 404

            cursor.execute(
                "SELECT A_Code, A_Name, Sel_Price, VahedCode, Exist FROM Article WHERE A_Code = ?",
                A_code,
            )
            article = cursor.fetchone()

            if not article:
                return jsonify({"error": "No article found"}), 404

            result = {
                "FldC_Kala": article.A_Code,
                "FldN_Kala": article.A_Name,
                "FldFee": article.Sel_Price,
                "VahedCode": article.VahedCode,
                "FldMande": article.Exist,
                "M_groupcode": m_group.M_groupcode,
                "M_groupname": m_group.M_groupname,
                "S_groupcode": s_group.S_groupcode,
                "S_groupname": s_group.S_groupname,
            }

            return jsonify(result)

        else:
            cursor.execute(
                "SELECT A_Code, A_Name, Sel_Price, VahedCode, Exist FROM Article WHERE A_Name LIKE ?",
                ("%" + A_code_or_name + "%",),
            )
            articles = cursor.fetchall()

            if not articles:
                return jsonify({"error": "No articles found"}), 404

            result = []
            for article in articles:
                A_Code = article.A_Code
                M_groupcode = A_Code[:2]
                S_groupcode = A_Code[2:4]

                cursor.execute(
                    "SELECT M_groupcode, M_groupname FROM M_Group WHERE M_groupcode = ?",
                    M_groupcode,
                )
                m_group = cursor.fetchone()

                cursor.execute(
                    "SELECT S_groupcode, S_groupname FROM S_GROUP WHERE S_groupcode = ?",
                    S_groupcode,
                )
                s_group = cursor.fetchone()

                if not m_group or not s_group:
                    continue

                result.append(
                    {
                        "FldC_Kala": article.A_Code,
                        "FldN_Kala": article.A_Name,
                        "FldFee": article.Sel_Price,
                        "FldN_Vahed": article.VahedCode,
                        "FldMande": article.Exist,
                        "M_groupcode": m_group.M_groupcode,
                        "M_groupname": m_group.M_groupname,
                        "S_groupcode": s_group.S_groupcode,
                        "S_groupname": s_group.S_groupname,
                    }
                )

            return jsonify(result)

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@Holoo_bp.route("/get_factures_by_c_code", methods=["POST"])
@require_api_key
def get_factures_by_c_code():
    data = request.get_json()

    if not data or "C_Code" not in data:
        return jsonify({"error": "C_Code is required"}), 400

    c_code = data["C_Code"]
    start_date = data.get("start_date", "1900-01-01")
    end_date = data.get("end_date", "2100-01-01")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM facture 
        WHERE C_Code = ? 
        AND Fac_Date BETWEEN ? AND ?
    """,
        (c_code, start_date, end_date),
    )

    factures = cursor.fetchall()

    if not factures:
        cursor.close()
        conn.close()
        return (
            jsonify(
                {
                    "error": f"No facture records found for C_Code {c_code} in this date range"
                }
            ),
            404,
        )

    columns_facture = [column[0] for column in cursor.description]
    result = []

    for facture in factures:
        fac_code = facture[0]
        facture_dict = {
            columns_facture[idx]: facture[idx] for idx in range(len(columns_facture))
        }

        # دریافت `factart`های مربوطه
        cursor.execute("SELECT * FROM factart WHERE Fac_Code = ?", (fac_code,))
        factarts = cursor.fetchall()
        columns_factart = [column[0] for column in cursor.description]
        factart_list = [
            {columns_factart[idx]: row[idx]
                for idx in range(len(columns_factart))}
            for row in factarts
        ]

        result.append({"facture": facture_dict, "factarts": factart_list})

    cursor.close()
    conn.close()

    return jsonify(result)


# لیست برای ذخیره اطلاعات چک‌ها در حافظه
checks_list = []


@Holoo_bp.route("/fetch_checks", methods=["POST"])
@require_api_key
def fetch_checks():
    try:
        # دریافت داده از درخواست
        data = request.get_json()

        # بررسی اینکه آیا C_Code_Source موجود است
        if not data or "C_Code_Source" not in data:
            return jsonify({"error": "C_Code_Source parameter is required"}), 400

        # استخراج C_Code_Source از داده‌های درخواست
        c_code_source = data["C_Code_Source"]

        # چاپ C_Code_Source برای بررسی
        print(f"Received C_Code_Source: {c_code_source}")

        # اتصال به دیتابیس
        conn = get_db_connection()
        cursor = conn.cursor()

        # اجرای کوئری برای دریافت چک‌های مربوط به C_Code_Source
        query = """
       SELECT 
        Check_Code, Back_Number, Export_Date, Attain_Date, Receive_Date,
        Check_Number, C_Code_Source, C_Code_Destination, Daryaft_Pardakht, 
        Sel_check, Vosool, DarJaryan, Cust, Bank_Code, Account_Number,
        Col_Code, Moien_Code, Tafzili_Code, Comm 
    FROM [Check]  
    WHERE C_Code_Source = ?
"""

        cursor.execute(query, (c_code_source,))
        checks = cursor.fetchall()

        # بررسی تعداد رکوردهای برگردانده شده
        print(f"Total records fetched: {len(checks)}")

        if len(checks) == 0:
            return (
                jsonify(
                    {"message": "No checks found for the provided C_Code_Source"}),
                404,
            )

        # تبدیل داده‌ها به فرمت JSON
        checks_list = [
            {
                "Check_Code": row.Check_Code,
                "Back_Number": row.Back_Number,
                "Export_Date": row.Export_Date,
                "Attain_Date": row.Attain_Date,
                "Receive_Date": row.Receive_Date,
                "Check_Number": row.Check_Number,
                "C_Code_Source": row.C_Code_Source,
                "C_Code_Destination": row.C_Code_Destination,
                "Daryaft_Pardakht": row.Daryaft_Pardakht,
                "Sel_check": row.Sel_check,
                "Vosool": row.Vosool,
                "DarJaryan": row.DarJaryan,
                "Cust": row.Cust,
                "Bank_Code": row.Bank_Code,
                "Account_Number": row.Account_Number,
                "Col_Code": row.Col_Code,
                "Moien_Code": row.Moien_Code,
                "Tafzili_Code": row.Tafzili_Code,
                "Comm": row.Comm,
            }
            for row in checks
        ]

        # چاپ داده‌ها قبل از بازگشت پاسخ
        print(f"Fetched Data: {checks_list}")

        # بستن اتصال به دیتابیس
        cursor.close()
        conn.close()

        # ارسال پاسخ
        return jsonify(
            {
                "message": "Checks fetched successfully",
                "count": len(checks_list),
                "data": checks_list,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def ensure_wc_table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        IF OBJECT_ID(N'dbo.{table_name}', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.{table_name} (
                Gift_ID INT IDENTITY(1,1) PRIMARY KEY,
                A_Code NVARCHAR(50),
                A_Code_C NVARCHAR(50),
                A_Name NVARCHAR(200),
                Model NVARCHAR(100),
                Buy_Price DECIMAL(18,2),
                Gift_Code NVARCHAR(50), 
                is_gift BIT DEFAULT 1,
                Created_At DATETIME DEFAULT GETDATE(),
                Quantity INT NULL,
                Threshold INT NULL
            )
        END
        """
    )
    conn.commit()


@Holoo_bp.route("/assign_gift", methods=["GET", "POST"])
@require_api_key
def assign_gift_if_eligible():
    fixed_table_name = "MyGift_WC"

    conn = get_db_connection()
    cursor = conn.cursor()

    # بررسی وجود ستون Visitor_Code در جدول
    ensure_visitor_column_exists(conn, fixed_table_name)

    if request.method == "GET":
        try:
            cursor.execute(f"SELECT * FROM dbo.{fixed_table_name}")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            conn.close()

    # POST method
    data = request.get_json()
    required_fields = ["A_Code", "quantity",
                       "gift_code", "threshold", "visitor_code"]
    missing_fields = [
        field for field in required_fields if not data.get(field)]
    if missing_fields:
        return (
            jsonify(
                {"error": "Missing required fields",
                    "missing_fields": missing_fields}
            ),
            400,
        )

    a_code = data.get("A_Code")
    quantity = int(data.get("quantity", 0))
    gift_code = data.get("gift_code")
    threshold = int(data.get("threshold", 0))
    visitor_code = data.get("visitor_code")

    try:
        # بررسی مجاز بودن ویزیتور
        cursor.execute(
            """
            SELECT WSetEshan FROM TblSetting_Visitori
            WHERE FldC_Visitor = ?
        """,
            (visitor_code,),
        )
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Visitor not found"}), 404
        if row[0] != 1:
            return jsonify({"error": "شما مجاز به ثبت این عملیات نیستید"}), 403

        # بررسی صلاحیت دریافت هدیه
        gift_count = quantity // threshold
        if gift_count < 1:
            return (
                jsonify(
                    {"error": "Not eligible for gift: quantity below threshold"}),
                400,
            )

        # دریافت اطلاعات کالا برای هدیه
        cursor.execute(
            """
            SELECT TOP 1 A_Code, A_Code_C, A_Name, Model, Buy_Price
            FROM dbo.Article
            WHERE A_Code = ?
        """,
            (gift_code,),
        )
        article = cursor.fetchone()

        if not article:
            return jsonify({"error": "Gift product not found"}), 404

        created_at = datetime.utcnow()

        # درج gift_count ردیف در جدول هدیه
        for _ in range(gift_count):
            cursor.execute(
                f"""
                INSERT INTO dbo.{fixed_table_name} (
                    A_Code, A_Code_C, A_Name, Model, Buy_Price,
                    Gift_Code, is_gift, Created_At, Quantity, Threshold, Visitor_Code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    a_code,
                    article.A_Code_C,
                    article.A_Name,
                    article.Model,
                    article.Buy_Price,
                    gift_code,
                    1,
                    created_at,
                    quantity,
                    threshold,
                    visitor_code,
                ),
            )

        conn.commit()

        return (
            jsonify(
                {
                    "message": f"{gift_count} gift(s) assigned successfully.",
                    "gift_count": gift_count,
                    "gift_code": gift_code,
                    "gift_name": article.A_Name,
                    "model": article.Model,
                    "visitor_code": visitor_code,
                    "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@Holoo_bp.route("/gift_report", methods=["POST"])
@require_api_key
def get_gift_report_by_visitor():
    data = request.get_json()
    visitor_code = str(data.get("visitor_code") or "").strip()

    if not visitor_code:
        return jsonify({"error": "visitor_code is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # اطمینان از وجود ستون visitor_code
        cursor.execute(
            """
            IF COL_LENGTH('MyGift_WC', 'visitor_code') IS NULL
            BEGIN
                ALTER TABLE MyGift_WC ADD visitor_code NVARCHAR(50)
            END
        """
        )
        conn.commit()

        cursor.execute(
            """
            SELECT A_Code, A_Name, Gift_Code, Quantity, Threshold, Created_At, visitor_code
            FROM dbo.MyGift_WC
            WHERE visitor_code = ?
        """,
            (visitor_code,),
        )
        rows = cursor.fetchall()

        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]

        return jsonify({"gifts": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


def ensure_visitor_column_exists(conn, table_name):
    cursor = conn.cursor()
    try:
        # بررسی وجود ستون با استفاده از COL_LENGTH
        cursor.execute(
            f"""
            IF COL_LENGTH('{table_name}', 'Visitor_Code') IS NULL
            BEGIN
                ALTER TABLE {table_name} ADD Visitor_Code NVARCHAR(50) NULL
            END
        """
        )
        conn.commit()
        print(f"✅ ستون Visitor_Code در جدول {table_name} بررسی یا اضافه شد.")
    except Exception as e:
        print(f"❌ خطا در بررسی یا افزودن ستون Visitor_Code: {e}")
    finally:
        cursor.close()


@Holoo_bp.route("/delete_gift", methods=["POST"])
@require_api_key
def delete_gift():
    data = request.get_json()
    gift_code = data.get("gift_code")
    a_code = data.get("A_Code")
    if not gift_code or not a_code:
        return jsonify({"error": "Fields 'A_Code' and 'gift_code' are required"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    table_name = "MyGift_WC"
    # بررسی وجود سطر با A_Code و Gift_Code مشخص
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM dbo.{table_name}
        WHERE A_Code = ? AND Gift_Code = ?
        """,
        (a_code, gift_code),
    )
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.close()
        conn.close()
        return (
            jsonify(
                {
                    "error": f"No gift found with A_Code '{a_code}' and Gift_Code '{gift_code}'"
                }
            ),
            400,
        )
    # حذف آن سطر
    cursor.execute(
        f"""
        DELETE FROM dbo.{table_name}
        WHERE A_Code = ? AND Gift_Code = ?
        """,
        (a_code, gift_code),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return (
        jsonify(
            {
                "message": f"Gift with A_Code '{a_code}' and Gift_Code '{gift_code}' deleted successfully"
            }
        ),
        200,
    )


@Holoo_bp.route("/assign_to_miniwarehouse", methods=["POST"])
@require_api_key
def assign_to_miniwarehouse():
    data = request.json
    visitor_code = data.get("visitor_code")
    items = data.get("items", [])

    if not visitor_code or not items:
        return jsonify({"error": "Missing visitor_code or items"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # بررسی مجاز بودن استفاده از انبارک
    cursor.execute(
        "SELECT WUseAnbarak FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
        (visitor_code,),
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Visitor code not found"}), 404

    use_anbarak = int(row[0]) if row[0] is not None else 0
    if use_anbarak != 1:
        conn.close()
        return jsonify({"error": "شما مجاز به استفاده از انبارک نیستید"}), 403

    # ساخت جدول انبارک در صورت عدم وجود
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='mini_warehouse' AND xtype='U'
        )
        BEGIN
            CREATE TABLE mini_warehouse (
                id INT IDENTITY(1,1) PRIMARY KEY,
                visitor_code NVARCHAR(50) NOT NULL,
                article_code NVARCHAR(50) NOT NULL,
                article_name NVARCHAR(255),
                quantity INT DEFAULT 0
            )
        END
    """
    )
    conn.commit()

    # گرفتن لیست کالاها از دیتابیس
    cursor.execute("SELECT A_Code, A_Name, Exist FROM Article")
    article_rows = cursor.fetchall()
    article_lookup = {row[0]: {"name": row[1], "exist": row[2]}
                      for row in article_rows}

    invalid_articles = []

    for item in items:
        article_code = item.get("article_code")
        quantity = item.get("quantity", 0)

        if quantity == 0:
            invalid_articles.append(
                {"article_code": article_code, "error": "Quantity cannot be zero"}
            )
            continue

        if article_code not in article_lookup:
            invalid_articles.append(
                {"article_code": article_code, "error": "Invalid article code"}
            )
            continue

        article_info = article_lookup[article_code]
        article_name = article_info["name"]
        article_exist = (
            int(article_info["exist"]) if article_info["exist"] not in [
                None, ""] else 0
        )

        if quantity > article_exist:
            invalid_articles.append(
                {
                    "article_code": article_code,
                    "error": f"Requested quantity ({quantity}) exceeds available stock ({article_exist})",
                }
            )
            continue

        cursor.execute(
            """
            SELECT id FROM mini_warehouse
            WHERE visitor_code = ? AND article_code = ?
            """,
            (visitor_code, article_code),
        )
        result = cursor.fetchone()

        if result:
            cursor.execute(
                """
                UPDATE mini_warehouse
                SET quantity = ?
                WHERE id = ?
                """,
                (quantity, result[0]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO mini_warehouse (visitor_code, article_code, article_name, quantity)
                VALUES (?, ?, ?, ?)
                """,
                (visitor_code, article_code, article_name, quantity),
            )

    if invalid_articles:
        conn.rollback()
        cursor.close()
        conn.close()
        return (
            jsonify({"error": "Some items were invalid",
                    "details": invalid_articles}),
            400,
        )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"}), 200


@Holoo_bp.route("/miniwarehouse/report", methods=["POST"])
@require_api_key
def miniwarehouse_report():
    try:
        data = request.get_json()
        visitor_code = data.get("visitor_code")

        if not visitor_code:
            return jsonify({"error": "visitor_code الزامی است"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی وجود ویزیتور
        cursor.execute(
            "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?", (
                visitor_code,)
        )
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "کد بازاریاب نامعتبر است"}), 404

        # گرفتن کالاهای موجود در انبارک بازاریاب
        cursor.execute(
            "SELECT article_code, quantity FROM mini_warehouse WHERE visitor_code = ?",
            (visitor_code,),
        )
        mini_items = cursor.fetchall()

        if not mini_items:
            conn.close()
            return (
                jsonify({"visitor_code": visitor_code,
                        "report": [], "count": 0}),
                200,
            )

        report = []

        for article_code, quantity in mini_items:
            cursor.execute(
                """
                SELECT a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist,
                       a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,
                       a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5,
                       a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                       a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton,
                       p.PicturePath
                FROM article a
                LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                WHERE a.A_Code = ?
                """,
                (article_code,),
            )

            row = cursor.fetchone()
            if not row:
                continue

            report.append(
                {
                    "CanEnterFee": True,
                    "EndBuyPrice": float(row[18] or 0),
                    "FldACode_C": row[1],
                    "FldC_Kala": row[0],
                    "FldFee": float(row[3] or 0),
                    "FldFeeBadAzTakhfif": float(row[3] or 0),
                    "FldImage": row[22] or "https://webcomco.com/logo.png",
                    "FldMande": int(row[5] or 0),
                    "FldMax": float(row[19] or 0),
                    "FldMin": float(row[20] or 0),
                    "FldN_Kala": row[2],
                    "FldN_Vahed": row[4] or "نامشخص",
                    "FldN_Vahed_Riz": "نامشخص",
                    "FldTedadKarton": int(row[21] or 0),
                    "FldTozihat": row[6] or "",
                    "FldVahedVazn": "نامشخص",
                    "IsGifted": False,
                    "Sel_Price2": float(row[9] or 0),
                    "Sel_Price3": float(row[10] or 0),
                    "Sel_Price4": float(row[11] or 0),
                    "Sel_Price5": float(row[12] or 0),
                    "Sel_Price6": float(row[13] or 0),
                    "Sel_Price7": float(row[14] or 0),
                    "Sel_Price8": float(row[15] or 0),
                    "Sel_Price9": float(row[16] or 0),
                    "Sel_Price10": float(row[17] or 0),
                    "FldTedad": quantity,
                }
            )

        conn.close()

        return (
            jsonify(
                {"visitor_code": visitor_code,
                    "report": report, "count": len(report)}
            ),
            200,
        )

    except Exception as e:
        logging.error(f"خطا در miniwarehouse_report: {str(e)}")
        return jsonify({"error": "خطای داخلی سرور", "details": str(e)}), 500


@Holoo_bp.route("/delete_from_miniwarehouse", methods=["POST"])
@require_api_key
def delete_from_miniwarehouse():
    data = request.json
    visitor_code = data.get("visitor_code")
    article_codes = data.get("article_codes")  # ← لیست کالاها

    if not visitor_code or not article_codes or not isinstance(article_codes, list):
        return (
            jsonify({"error": "Missing or invalid visitor_code or article_codes"}),
            400,
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # بررسی کالاهایی که واقعاً وجود دارند برای این ویزیتور
        placeholders = ",".join("?" for _ in article_codes)
        params = [visitor_code] + article_codes
        cursor.execute(
            f"""
            SELECT article_code
            FROM mini_warehouse
            WHERE visitor_code = ? AND article_code IN ({placeholders})
            """,
            params,
        )
        found_articles = [row[0] for row in cursor.fetchall()]

        if not found_articles:
            return jsonify({"error": "No matching records found"}), 404

        # حذف کالاهای موجود
        placeholders = ",".join("?" for _ in found_articles)
        params = [visitor_code] + found_articles
        cursor.execute(
            f"""
            DELETE FROM mini_warehouse
            WHERE visitor_code = ? AND article_code IN ({placeholders})
            """,
            params,
        )
        conn.commit()

        return (
            jsonify(
                {
                    "status": "deleted",
                    "visitor_code": visitor_code,
                    "deleted_articles": found_articles,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@Holoo_bp.route("/miniwarehouse/<visitor_code>", methods=["GET"])
@require_api_key
def get_miniwarehouse_report(visitor_code):
    conn = get_db_connection()
    cursor = conn.cursor()

    # بررسی ویزیتور
    cursor.execute(
        "SELECT FldN_Visitor FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
        (visitor_code,),
    )
    visitor = cursor.fetchone()
    if not visitor:
        conn.close()
        return jsonify({"error": "Visitor not found"}), 404

    visitor_name = visitor[0]

    # کوئری گرفتن کالاها به همراه نام گروه
    cursor.execute(
        """
        SELECT 
            mw.article_code,
            mw.article_name,
            mw.quantity,
            a.Sel_Price,
            sg.S_groupname
        FROM mini_warehouse mw
        JOIN Article a ON mw.article_code = a.A_Code
        LEFT JOIN S_GROUP sg 
            ON LEFT(a.A_Code, 2) = sg.M_groupcode 
           AND SUBSTRING(a.A_Code, 3, 2) = sg.S_groupcode
        WHERE mw.visitor_code = ?
    """,
        (visitor_code,),
    )

    rows = cursor.fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "article_code": row[0],
                "article_name": row[1],
                "quantity": row[2],
                "sel_price": row[3],
                "group_name": row[4] or "نامشخص",
            }
        )

    conn.close()

    return (
        jsonify(
            {
                "visitor_code": visitor_code,
                "visitor_name": visitor_name,
                "items": items,
                "total_items": len(items),
            }
        ),
        200,
    )


@Holoo_bp.route("/Get_Changed_Articles_ByDate", methods=["GET"])
@require_api_key
def get_changed_articles_by_date():
    """
    دریافت کالاهایی که از یک تاریخ خاص به بعد تغییر کرده‌اند
    """
    try:
        since = request.args.get("since")  # مثلاً "2024-06-01T00:00:00"
        if not since:
            return jsonify({"error": "Missing 'since' parameter"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT A_Code, A_Name, Sel_Price, Exist, ModifyDate
            FROM Article
            WHERE ModifyDate >= ? AND IsActive = 1
            ORDER BY ModifyDate DESC
        """,
            (since,),
        )

        rows = cursor.fetchall()
        articles = []
        for row in rows:
            articles.append(
                {
                    "A_Code": row[0],
                    "A_Name": row[1],
                    "Sel_Price": float(row[2]) if row[2] else 0,
                    "Exist": float(row[3]) if row[3] else 0,
                    "ModifyDate": (
                        row[4].strftime(
                            "%Y-%m-%d %H:%M:%S") if row[4] else None
                    ),
                }
            )

        return jsonify({"count": len(articles), "articles": articles})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# تابع ساخت فیلد update_wc
def ensure_update_wc_column_exists(conn, table_name="Article"):
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            IF COL_LENGTH('{table_name}', 'update_wc') IS NULL
            BEGIN
                ALTER TABLE {table_name} ADD update_wc BIT NOT NULL DEFAULT 0 WITH VALUES;
            END
        """
        )
        print("✅ ستون update_wc بررسی و ساخته شد (در صورت نیاز)")
    except Exception as e:
        print(f"❌ خطا در ساخت فیلد update_wc: {str(e)}")


def ensure_update_wc_trigger_exists(conn, table_name="Article"):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COUNT(*) FROM sys.triggers WHERE name = 'trg_set_update_wc'
        """
        )
        exists = cursor.fetchone()[0]

        if exists == 0:
            cursor.execute(
                f"""
                EXEC('
                    CREATE TRIGGER trg_set_update_wc
                    ON {table_name}
                    AFTER UPDATE
                    AS
                    BEGIN
                        SET NOCOUNT ON;

                        UPDATE A
                        SET update_wc = 1
                        FROM {table_name} A
                        JOIN inserted i ON A.A_Code = i.A_Code
                        JOIN deleted d ON d.A_Code = i.A_Code
                        WHERE 
                            ISNULL(i.Sel_Price, '''') <> ISNULL(d.Sel_Price, '''') OR
                            ISNULL(i.Exist, '''')     <> ISNULL(d.Exist, '''')     OR
                            ISNULL(i.A_Name, '''')    <> ISNULL(d.A_Name, '''')    OR
                            ISNULL(i.A_Code_C, '''')  <> ISNULL(d.A_Code_C, '''')
                    END
                ')
            """
            )
            print("✅ تریگر trg_set_update_wc ساخته شد.")
        else:
            print("ℹ️ تریگر trg_set_update_wc قبلاً وجود دارد.")
    except Exception as e:
        print(f"❌ خطا در ساخت تریگر: {str(e)}")


@Holoo_bp.route("/init_wc_support", methods=["GET"])
@require_api_key
def init_wc_support():
    try:
        conn = get_db_connection()
        ensure_update_wc_column_exists(conn)
        ensure_update_wc_trigger_exists(conn)
        conn.commit()
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "فیلد و تریگر ساخته شدند (در صورت نیاز)",
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        if "conn" in locals():
            conn.close()


# متد اصلی
@Holoo_bp.route("/Get_Changed_Articles_Instant", methods=["GET"])
@require_api_key
def get_changed_articles_instant():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. ساخت فیلد و تریگر
        ensure_update_wc_column_exists(conn)
        ensure_update_wc_trigger_exists(conn)

        # 2. دریافت کالاهای تغییر کرده
        cursor.execute(
            """
            SELECT A_Code, A_Name, Sel_Price, Exist, ModifyDate
            FROM Article
            WHERE update_wc = 1 AND IsActive = 1
            ORDER BY ModifyDate DESC
        """
        )
        rows = cursor.fetchall()

        articles = []
        changed_codes = []

        for row in rows:
            articles.append(
                {
                    "A_Code": row[0],
                    "A_Name": row[1],
                    "Sel_Price": float(row[2]) if row[2] else 0,
                    "Exist": float(row[3]) if row[3] else 0,
                    "ModifyDate": (
                        row[4].strftime(
                            "%Y-%m-%d %H:%M:%S") if row[4] else None
                    ),
                }
            )
            changed_codes.append(row[0])

        # 3. صفر کردن update_wc
        if changed_codes:
            format_strings = ",".join("?" for _ in changed_codes)
            cursor.execute(
                f"""
                UPDATE Article SET update_wc = 0
                WHERE A_Code IN ({format_strings})
            """,
                changed_codes,
            )
            conn.commit()

        return (
            jsonify(
                {
                    "field_created": True,
                    "trigger_created": True,
                    "count": len(articles),
                    "articles": articles,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/save", methods=["POST"])
@require_api_key
def save_factors_to_holoo():
    try:
        data = request.get_json()

        order_title = data.get("OrderTitle", {})
        items = data.get("OrderDetails", [])

        if not order_title or not items:
            return jsonify({"error": "اطلاعات ناقص است"}), 400

        mobile = order_title.get("FldMobile")
        visitor_code = order_title.get("FldC_Visitor")
        is_return = order_title.get("IsReturn") == True

        if not mobile:
            return jsonify({"error": "شماره موبایل اجباری است"}), 400

        customer_code = get_customer_code_by_mobile(mobile)
        if not customer_code:
            return (
                jsonify({"error": "کد مشتری یافت نشد یا شماره موبایل نامعتبر است"}),
                400,
            )

        factor_id = generate_four_digit_factor_id()

        # اینجا حتما visitor_code رو پاس بده
        rq_index = insert_factor(
            order_title, customer_code, factor_id, is_return, visitor_code
        )

        inserted_items, blocked_items = insert_order_details(
            rq_index, items, visitor_code, is_return
        )

        if inserted_items:
            return (
                jsonify(
                    {
                        "status": "سفارش ثبت شد",
                        "RqIndex": rq_index,
                        "FactorID": factor_id,
                        "InsertedItems": inserted_items,
                        "BlockedItems": blocked_items,
                    }
                ),
                200,
            )
        elif blocked_items and not inserted_items:
            return (
                jsonify(
                    {
                        "error": "شما مجاز به ثبت بیش از موجودی نیستید",
                        "BlockedItems": blocked_items,
                    }
                ),
                400,
            )
        else:
            return (
                jsonify({"error": "هیچ کالایی ثبت نشد",
                        "details": "اطلاعات نامعتبر"}),
                400,
            )

    except Exception as e:
        logging.error(f"خطا در save_factors_to_holoo: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


def generate_four_digit_factor_id():
    return f"F-{random.randint(1000, 9999)}"


def get_customer_code_by_mobile(mobile):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT C_Code FROM CUSTOMER WHERE C_Mobile = ?", (mobile,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def can_sell_more_than_stock(visitor_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT FldP_ForooshBishAzMojoodi FROM TblSetting_Visitori WHERE FldC_Visitor = ?",
        (visitor_code,),
    )
    row = cursor.fetchone()
    conn.close()
    value = int(row[0]) if row and row[0] is not None else 0
    logging.debug(
        f"[DEBUG] اجازه فروش بیش از موجودی برای {visitor_code} = {value}")
    return value == 1


def get_current_stock(a_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Exist FROM ARTICLE WHERE A_Code = ?", (a_code,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0


def insert_factor(
    order_title, customer_code, factor_id, is_return, visitor_code=None, WEBCOM=1
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()
        default_date = datetime(1899, 12, 30)
        payment_type_text = "نقدی" if order_title.get(
            "FldPayId") == "1" else "نسیه"
        comment = order_title.get("FldTozihFaktor", "") + \
            f" ({payment_type_text})"

        # گرفتن آخرین RqIndex2 و ساخت مقدار جدید
        cursor.execute("SELECT ISNULL(MAX(RqIndex2), 0) FROM RQTITLE")
        max_rqindex2 = cursor.fetchone()[0] or 0
        new_rqindex2 = max_rqindex2 + 1

        # کوئری INSERT با ستون Visitor_Code
        cursor.execute(
            """
    INSERT INTO RQTITLE (
        RqType, R_CusCode, R_Date, T_Time, T_Date,
        SumPrice, Comment, FTakhfif, ShowOrHide, Beianeh,
        OkModir, UserName, RQT_Id, Wait, R_Time, FactorID, PaymentType,
        RqIndex2, Visitor_Code, Vaseteh_Code, WEBCOM
    ) OUTPUT INSERTED.RqIndex VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
            (
                "F" if not is_return else "R",       # RqType
                customer_code,                       # R_CusCode
                now,                                 # R_Date
                default_date,                        # T_Time
                now,                                 # T_Date
                order_title.get("FldTotalFaktor", 0),  # SumPrice
                comment,                             # Comment
                0,                                   # FTakhfif
                1,                                   # ShowOrHide
                0,                                   # Beianeh
                0,                                   # OkModir
                1,                                   # UserName
                0,                                   # RQT_Id
                0,                                   # Wait
                now,                                 # R_Time
                factor_id,                           # FactorID
                payment_type_text,                   # PaymentType
                new_rqindex2,                        # RqIndex2
                visitor_code,                        # Visitor_Code
                visitor_code,                        # Vaseteh_Code
                WEBCOM,                              # WEBCOM
            ),
        )

        rq_index_row = cursor.fetchone()
        if rq_index_row is None or rq_index_row[0] is None:
            raise Exception("Failed to retrieve RqIndex after insert")
        rq_index = rq_index_row[0]

        conn.commit()
        return rq_index

    except Exception as e:
        logging.error(f"خطا در insert_factor: {e}")
        raise

    finally:
        conn.close()


def excel_date(dt):
    temp = datetime(1899, 12, 30)
    delta = dt - temp
    return float(delta.days) + (float(delta.seconds) / 86400)


def insert_order_details(rq_index, items, visitor_code=None, is_return=False):
    """
    سفارشات را در RQDETAIL درج می‌کند و موجودی را به‌صورت مستقیم
    در جدول ARTICLE به‌روزرسانی می‌کند (بدون تریگر).
    """
    if not items:
        return [], []

    conn = None
    try:
        conn = get_db_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        item_codes = [item.get("FldC_Kala") or item.get("A_Code")
                      for item in items]

        # دریافت موجودی فعلی کالاها
        sql_fetch = f"""
            SELECT A_Code, A_Name, A_Code_C, VahedCode, ISNULL(Exist, 0) AS Exist 
            FROM ARTICLE WHERE A_Code IN ({','.join(['?'] * len(item_codes))})
        """
        cursor.execute(sql_fetch, item_codes)
        articles_db_info = {row.A_Code: row for row in cursor.fetchall()}

        allow_overstock = can_sell_more_than_stock(
            visitor_code) if visitor_code else False

        params_for_insert = []
        blocked_items_info = []
        stock_updates = []  # [(a_code, tedad)] برای بروزرسانی موجودی

        for item in items:
            a_code = item.get("FldC_Kala") or item.get("A_Code")
            try:
                tedad = int(item.get("FldTedad", 0))
            except ValueError:
                blocked_items_info.append(
                    {"code": a_code, "reason": "تعداد نامعتبر"})
                continue

            if a_code not in articles_db_info:
                blocked_items_info.append(
                    {"code": a_code, "reason": "کالای نامعتبر"})
                continue

            current_stock = float(articles_db_info[a_code].Exist or 0)
            if not is_return and not allow_overstock:
                if tedad > current_stock:
                    blocked_items_info.append(
                        {"code": a_code, "reason": f"موجودی ناکافی ({current_stock})"})
                    continue

            article_info = articles_db_info[a_code]
            insert_tuple = (
                rq_index, "F" if not is_return else "R", a_code, article_info.A_Code_C, article_info.A_Name,
                tedad, float(item.get("FldFee", 0)), article_info.VahedCode, item.get(
                    "FldTozihat", "")
            )
            params_for_insert.append(insert_tuple)

            # به‌روزرسانی موجودی: کم یا زیاد
            stock_updates.append((a_code, tedad if not is_return else -tedad))

        if blocked_items_info:
            conn.rollback()
            return [], blocked_items_info

        if params_for_insert:
            insert_query = """
                INSERT INTO RQDETAIL (
                    RqIndex, RqType, R_ArCode, R_ArCode_C, R_ArName, R_Few, R_Cost, Unit_Code, R_Commen,
                    R_FewAval, R_Few2, R_FewAval2, Show_Or_Hide, OkReceive, IndexHlp, Selected, 
                    RQ_State, R_FewAval3, R_Few3, FewKarton, FewBasteh, Moddat, DarsadTakhfif, TakhfifSatriR
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """
            cursor.executemany(insert_query, params_for_insert)

            # کاهش/افزایش موجودی برای هر کالا
            for a_code, tedad in stock_updates:
                cursor.execute("""
                    UPDATE ARTICLE SET Exist = ISNULL(Exist, 0) - ? WHERE A_Code = ?
                """, (tedad, a_code))

            conn.commit()
            inserted_codes = [p[2] for p in params_for_insert]
            return inserted_codes, []

        return [], []

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"خطا در insert_order_details: {e}", exc_info=True)
        return [], [{"code": "همه کالاها", "reason": f"خطای سیستمی: {e}"}]
    finally:
        if conn:
            conn.close()


@Holoo_bp.route("/Report_Customer", methods=["POST"])
@require_api_key
def report_customer_orders():
    data = request.get_json()

    customer_code = str(data.get("Customer_Code") or "").strip()
    visitor_code = str(data.get("Visitor_Code") or "").strip()
    from_date = str(data.get("From_Date") or "").strip()
    to_date = str(data.get("To_Date") or "").strip()

    if not customer_code or not visitor_code:
        return jsonify({"error": "Customer_Code and Visitor_Code are required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                t.RqIndex, t.RqType, t.R_CusCode, t.R_Date, t.T_Date, t.SumPrice, t.Visitor_Code, t.FactorID,
                d.RqIndex AS DetailRqIndex, d.RqType AS DetailRqType,
                d.R_ArCode, d.R_ArName, d.R_Few, d.R_Cost
            FROM RQTITLE t
            LEFT JOIN RQDETAIL d ON d.RqIndex = t.RqIndex  -- اصلاح این خط
            WHERE t.R_CusCode = ? AND t.Visitor_Code = ?
        """

        params = [customer_code, visitor_code]

        if from_date.lower() != "all" and to_date.lower() != "all":
            query += " AND CONVERT(DATE, t.R_Date, 120) BETWEEN ? AND ?"
            params.extend([from_date, to_date])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        orders = {}
        for row in rows:
            rq_index = row.RqIndex

            if rq_index not in orders:
                orders[rq_index] = {
                    "RQTITLE": {
                        "RqIndex": row.RqIndex,
                        "RqType": row.RqType,
                        "R_CusCode": row.R_CusCode,
                        "R_Date": str(row.R_Date),
                        "T_Date": str(row.T_Date),
                        "SumPrice": row.SumPrice,
                        "Visitor_Code": row.Visitor_Code,
                        "FactorID": row.FactorID,
                    },
                    "RQDETAIL": [],
                }

            # فقط وقتی رکورد جزئیات وجود دارد، اضافه شود
            if row.DetailRqIndex is not None:
                orders[rq_index]["RQDETAIL"].append(
                    {
                        "RqIndex": row.DetailRqIndex,
                        "RqType": row.DetailRqType,
                        "R_ArCode": row.R_ArCode,
                        "R_ArName": row.R_ArName,
                        "R_Few": row.R_Few,
                        "R_Cost": row.R_Cost,
                    }
                )

        return jsonify({"Orders": list(orders.values())}), 200

    except Exception as e:
        logging.error(f"report_customer_orders error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@Holoo_bp.route("/customer-location", methods=["POST"])
@require_api_key
def save_customer_location():
    try:
        data = request.get_json()

        customer_code = data.get("CustomerCode")
        visitor_code = data.get("VisitorCode")
        latitude = data.get("Latitude")
        longitude = data.get("Longitude")
        timestamp = data.get("Timestamp") or datetime.now()

        # بررسی اولیه
        if (
            not customer_code
            or not visitor_code
            or latitude is None
            or longitude is None
        ):
            return jsonify({"error": "اطلاعات ناقص است"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی اجازه ثبت GPS برای ویزیتور
        cursor.execute(
            """
            SELECT FldSabtGpsShakhs
            FROM TblSetting_Visitori
            WHERE FldC_Visitor = ?
        """,
            (visitor_code,),
        )
        row = cursor.fetchone()

        if not row or int(row[0]) != 1:
            return jsonify({"error": "شما مجاز به ثبت موقعیت مشتری نیستید"}), 403

        # ساخت جدول در صورت عدم وجود
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT * FROM sys.tables WHERE name = 'Customer_Location'
            )
            BEGIN
                CREATE TABLE Customer_Location (
                    Id INT IDENTITY(1,1) PRIMARY KEY,
                    CustomerCode NVARCHAR(15),
                    Latitude REAL,
                    Longitude REAL,
                    Timestamp DATETIME
                )
            END
        """
        )
        conn.commit()

        # درج موقعیت
        cursor.execute(
            """
            INSERT INTO Customer_Location (CustomerCode, Latitude, Longitude, Timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (customer_code, latitude, longitude, timestamp),
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "موقعیت مشتری ذخیره شد"}), 200

    except Exception as e:
        logging.error(f"خطا در save_customer_location: {str(e)}")
        return jsonify({"error": "خطای داخلی سرور", "details": str(e)}), 500

        def ensure_customer_visitor_table_exists(conn):
            cursor = conn.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT * FROM sys.tables WHERE name = 'CUSTOMER_VISITOR' AND schema_id = SCHEMA_ID('dbo')
                )
                BEGIN
                    CREATE TABLE dbo.CUSTOMER_VISITOR (
                        ID INT IDENTITY(1,1) PRIMARY KEY,
                        C_Code NVARCHAR(50) NOT NULL,
                        V_Code NVARCHAR(50) NOT NULL,
                        Assigned_At DATETIME NULL
                    );
                END
                """
            )
            conn.commit()
            cursor.close()


@Holoo_bp.route("/location", methods=["POST"])
@require_api_key
def save_location():
    try:
        data = request.get_json()

        visitor_code = data.get("VisitorCode")
        latitude = data.get("Latitude")
        longitude = data.get("Longitude")
        timestamp = data.get("Timestamp")  # اختیاری

        if not visitor_code or latitude is None or longitude is None:
            return jsonify({"error": "اطلاعات موقعیت ناقص است"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # بررسی و ساخت جدول اگر وجود نداشت
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT * FROM sys.tables WHERE name = 'Visitor_Location'
            )
            BEGIN
                CREATE TABLE Visitor_Location (
                    Id INT IDENTITY(1,1) PRIMARY KEY,
                    VisitorCode NVARCHAR(10),
                    Latitude REAL,
                    Longitude REAL,
                    Timestamp DATETIME
                )
            END
        """
        )
        conn.commit()

        # ذخیره موقعیت
        cursor.execute(
            """
            INSERT INTO Visitor_Location (VisitorCode, Latitude, Longitude, Timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (visitor_code, latitude, longitude, timestamp or datetime.now()),
        )

        conn.commit()
        conn.close()

        return jsonify({"status": "موقعیت ذخیره شد"}), 200

    except Exception as e:
        logging.error(f"خطا در save_location: {str(e)}")
        return jsonify({"error": "خطای داخلی سرور", "details": str(e)}), 500


def ensure_table_exists(cursor):
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'TblSetting_Visitori'
        )
        BEGIN
            CREATE TABLE TblSetting_Visitori (
                FldC_Visitor NVARCHAR(50) PRIMARY KEY,
                FldMob NVARCHAR(50),
                FldN_Visitor NVARCHAR(100),
                WDarsadSoud DECIMAL(10,2),
                WMandeHesab DECIMAL(18,2),
                FldVahedpool NVARCHAR(50),
                FldP_ForooshBishAzMojoodi BIT,
                FldS_Foroosh BIT,
                FldGps BIT,
                FldShowMande BIT,
                FldNewMoshtari BIT,
                FldSignature BIT,
                FldShowBedehkaran BIT,
                FldMarjooii BIT,
                FldVoroodTozihKala BIT,
                FldDoVahedi BIT,
                FldTracker BIT,
                FldTimeTrack NVARCHAR(50),
                FldSabtGpsShakhs BIT,
                FldShowGpsShakhs BIT,
                FldAutoRecive BIT,
                FldTimeRecive NVARCHAR(50),
                FldNameForooshgah NVARCHAR(100),
                FldTellForooshgah NVARCHAR(50),
                FldAddressForooshgah NVARCHAR(200),
                FldToken NVARCHAR(100),
                FldKharidBiashAz NVARCHAR(50),
                FldDarsadTakhfifRiali DECIMAL(10,2),
                FldEtelaResani BIT,
                FldZamanTahvil NVARCHAR(50),
                WSetTip NVARCHAR(50),
                WEnterFee NVARCHAR(50),
                WIsModir BIT,
                WSetEshan BIT,
                WHideBMande BIT,
                WShowMoiens BIT,
                WMegaModir BIT,
                WUseAnbarak BIT,
                ShowEndBuyPrice BIT,
                AddFactorComment NVARCHAR(200),
                IsPos BIT,
                FldStartWork NVARCHAR(50),
                FldEndWork NVARCHAR(50),
                ShowReport BIT
            )
        END
    """
    )


def sync_visitors(cursor):
    cursor.execute(
        """
        SELECT C_Mobile, C_Name, C_Code, Vaseteh_Porsant
        FROM CUSTOMER
        WHERE C_Mobile IS NOT NULL AND C_Mobile != ''
          AND C_Name IS NOT NULL AND C_Name != ''
          AND C_Code IS NOT NULL AND C_Code != ''
          AND Vaseteh = 1 AND City_Code IS NOT NULL
    """
    )
    customers = cursor.fetchall()

    inserted, updated = 0, 0
    for row in customers:
        mobile, name, code, porsant = row
        cursor.execute(
            "SELECT 1 FROM TblSetting_Visitori WHERE FldC_Visitor = ?", (code,)
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE TblSetting_Visitori
                SET FldMob = ?, FldN_Visitor = ?, WDarsadSoud = ?
                WHERE FldC_Visitor = ?
            """,
                (mobile, name, porsant or 0, code),
            )
            updated += 1
        else:
            cursor.execute(
                """
                INSERT INTO TblSetting_Visitori (
                    FldC_Visitor, FldMob, FldN_Visitor, WDarsadSoud, WMandeHesab, FldVahedpool, FldEtelaResani, FldZamanTahvil
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    code,
                    mobile,
                    name,
                    porsant or 0,
                    0,
                    "ریال",
                    1,
                    "تحویل 24 ساعت پس از فاکتور",
                ),
            )
            inserted += 1

    print(f"✔️ ویزیتورها: {updated} به‌روزرسانی، {inserted} اضافه شد")


def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_table_exists(cursor)
        sync_visitors(cursor)
        conn.commit()
    except Exception as e:
        print("❌ خطا در setup_database:", e)
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@Holoo_bp.route("/location", methods=["GET"])
@require_api_key
def get_location():
    """
    Retrieves location information from Visitor_Location based on VisitorCode.
    Expected query parameter: VisitorCode
    """
    try:
        visitor_code = request.args.get("VisitorCode")

        if not visitor_code:
            return jsonify({"error": "کد ویزیتور (VisitorCode) الزامی است"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Query the Visitor_Location table for the given VisitorCode
        cursor.execute(
            """
            SELECT 
                VisitorCode, Latitude, Longitude, Timestamp
            FROM Visitor_Location
            WHERE VisitorCode = ?
            ORDER BY Timestamp DESC -- Order by timestamp to get most recent first
            """,
            (visitor_code,)
        )

        location_data = cursor.fetchall()
        conn.close()

        if location_data:
            # Map the fetched data to a list of dictionaries for a structured JSON response
            locations = []
            for row in location_data:
                locations.append({
                    "VisitorCode": row[0],
                    "Latitude": row[1],
                    "Longitude": row[2],
                    "Timestamp": row[3].isoformat() if isinstance(row[3], datetime) else row[3]
                })

            return jsonify(locations), 200
        else:
            return jsonify({"error": "موقعیت مکانی برای کد ویزیتور مشخص شده یافت نشد"}), 404

    except Exception as e:
        logging.error(f"خطا در get_location: {str(e)}")
        return jsonify({"error": "خطای داخلی سرور", "details": str(e)}), 500


if __name__ == "__main__":
    app.register_blueprint(Holoo_bp)  # این خیلی مهمه!
    app.run(host="0.0.0.0", port=8200, debug=True)
