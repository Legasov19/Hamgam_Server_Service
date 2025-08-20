
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response,send_file
from flask import Response
from flask_restx import Api, Resource, fields, reqparse
from datetime import datetime, time, timedelta
from decorators import login_required
import pyodbc
import csv
import os
import math
from functools import wraps
import json
import shutil
import requests
import random
from PIL import Image
import sys
from flask_cors import cross_origin
from bs4 import BeautifulSoup
import re
import urllib
# from forms import Buttons, GroupSelectionForm
from flask import make_response , g
import traceback, logging, datetime
from contextlib import closing
from datetime import datetime
# from routes.login import full_login_required
from routes.config_utils import ( 
    save_db_config,
    load_db_config,
    get_article_connection,
    get_main_db_connection1,
    get_second_db_connection1
)


# تعریف بلوپرینت
holoo_bp = Blueprint('holoo', __name__)


#def
# -----------------------------
# دکوراتور بررسی API Key

user_databases = {}
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

def get_converted_article_prices():
    """
    Connects to the database, retrieves price fields from the Article table,
    checks the currency unit in TblSetting_forooshgahi, and converts prices
    from Toman to Rial if necessary.

    Returns:
        A list of dictionaries, where each dictionary represents an article
        and contains its price fields, with prices converted to Rial if the
        currency setting is Toman. Returns an empty list if an error occurs.
    """
    conn = None
    cursor = None
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # 1. Get the currency setting
        cursor.execute("SELECT FldVahedpool FROM TblSetting_forooshgahi")
        currency_setting = cursor.fetchone()
        
        is_toman = False
        if currency_setting and str(currency_setting[0]).strip().lower() == 'تومان': # Ensure case-insensitivity and stripping
            is_toman = True

        # 2. Retrieve prices from the Article table
        price_fields = [
            "FirstBuy_Price", "EndBuy_Price", "Sel_Price", "Sel_Price2",
            "Sel_Price3", "Sel_Price4", "Sel_Price5", "Sel_Price6",
            "Sel_Price7", "Sel_Price8", "Sel_Price9", "Sel_Price10",
            "A_Code", "A_Code_C", "A_Name", "VahedCode", "Exist", "Karton",
            "Attribute", "DarsadTakhfif", "PriceTakhfif", "A_Max", "A_Min", "Image" # Add other fields you need
        ]
        
        query = f"SELECT {', '.join(price_fields)} FROM Article WHERE IsActive = 1"
        cursor.execute(query)
        
        articles_raw_data = []
        for row in cursor.fetchall():
            article = {}
            for i, field in enumerate(price_fields):
                value = row[i]
                
                # Apply conversion only to price fields
                if field in ["FirstBuy_Price", "EndBuy_Price", "Sel_Price", "Sel_Price2",
                             "Sel_Price3", "Sel_Price4", "Sel_Price5", "Sel_Price6",
                             "Sel_Price7", "Sel_Price8", "Sel_Price9", "Sel_Price10"] and value is not None:
                    try:
                        numeric_value = float(value)
                        if is_toman:
                            article[field] = numeric_value * 10 # Convert Toman to Rial
                        else:
                            article[field] = numeric_value
                    except (ValueError, TypeError):
                        article[field] = None # Handle non-numeric or invalid price values
                else:
                    article[field] = value
            articles_raw_data.append(article)
            
        return articles_raw_data

    except Exception as e:
        print(f"An error occurred in get_converted_article_prices: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


'''
Example
        all_articles = get_converted_article_prices()

'''

def fetch_best_selling_data(R_Date):
    conn = get_article_connection()
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
        
        
        
        
def add_logo_column():
    conn = get_article_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'TblSetting_forooshgahi' 
                  AND COLUMN_NAME = 'Logo'
            )
            BEGIN
                ALTER TABLE TblSetting_forooshgahi 
                ADD Logo NVARCHAR(512) NULL
            END
        """)
        conn.commit()
    except Exception as e:
        print(f"خطا در اضافه کردن ستون Logo: {e}")
    finally:
        cursor.close()
        conn.close()

        
        

def create_tblsetting_forooshgahi():
    query = """
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = 'TblSetting_forooshgahi'
    )
    BEGIN
        CREATE TABLE TblSetting_forooshgahi (
            WMandeHesab BIT NULL,
            FldVahedpool NVARCHAR(50) NULL,
            FldP_ForooshBishAzMojoodi BIT NULL,
            FldMarjooii BIT NULL,
            FldTaiidAdmin BIT NULL,
            FldNameForooshgah NVARCHAR(100) NULL,
            FldTellForooshgah NVARCHAR(50) NULL,
            FldAddressForooshgah NVARCHAR(200) NULL,
            FldKharidBiashAz NVARCHAR(50) NULL,
            FldZamanTahvil NVARCHAR(50) NULL,
            WSetTip NVARCHAR(50) NULL,
            WSetEshan BIT NULL,
            WShowMoiens BIT NULL,
            AddFactorComment NVARCHAR(200) NULL,
            ShowReport BIT NULL
        )
    END;

    IF NOT EXISTS (SELECT * FROM TblSetting_forooshgahi)
    BEGIN
        INSERT INTO TblSetting_forooshgahi (
            WMandeHesab,
            FldVahedpool,
            FldP_ForooshBishAzMojoodi,
            FldMarjooii,
            FldTaiidAdmin,
            FldNameForooshgah,
            FldTellForooshgah,
            FldAddressForooshgah,
            FldKharidBiashAz,
            FldZamanTahvil,
            WSetTip,
            WSetEshan,
            WShowMoiens,
            AddFactorComment,
            ShowReport
        ) VALUES (
            NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        )
    END;
    """

    try:
        conn = get_article_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        print("✅ TblSetting_forooshgahi created and default row inserted (if needed).")
    except Exception as e:
        print("❌ Error creating or initializing TblSetting_forooshgahi:", e)
    finally:
        cursor.close()
        conn.close()
        
        
        
def hide_exist_column():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود ستون HideExist
        cursor.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'TblSetting_forooshgahi' AND COLUMN_NAME = 'HideExist'
        """)
        exists = cursor.fetchone()

        if exists:
            print("ستون HideExist قبلاً وجود دارد.")
        else:
            # افزودن ستون
            cursor.execute("""
                ALTER TABLE TblSetting_forooshgahi
                ADD HideExist BIT NULL
            """)
            conn.commit()
            print("ستون HideExist با موفقیت اضافه شد.")

    except Exception as e:
        print(f"خطا در اضافه کردن ستون: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
            
#اضافه کردن ستون اکسپایر لاگین به جدول ستینگ فروشگاهی
def add_expirelogin_column():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود ستون قبل از افزودن
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'TblSetting_forooshgahi' AND COLUMN_NAME = 'ExpireLogin'
        """)
        if cursor.fetchone():
            print("ستون ExpireLogin قبلاً وجود دارد.")
        else:
            cursor.execute("""
                ALTER TABLE TblSetting_forooshgahi 
                ADD ExpireLogin BIT DEFAULT 0
            """)
            conn.commit()
            print("ستون ExpireLogin با موفقیت اضافه شد.")

        cursor.close()
        conn.close()
    except Exception as e:
        print("خطا در افزودن ستون:", str(e))


        
def create_mgroup_image_column():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # چک کردن وجود ستون
        check_query = """
        SELECT 1 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'M_GROUP' AND COLUMN_NAME = 'Image'
        """
        cursor.execute(check_query)
        exists = cursor.fetchone()

        if exists:
            print('ستون Image از قبل وجود دارد')
            return 'ستون Image از قبل وجود دارد'

        # ایجاد ستون
        alter_query = "ALTER TABLE M_GROUP ADD Image NVARCHAR(255) NULL"
        cursor.execute(alter_query)

        # مقداردهی اولیه
        image_url = "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
        update_query = "UPDATE M_GROUP SET Image = ?"
        cursor.execute(update_query, (image_url,))

        conn.commit()
        print('ستون Image ایجاد شد و مقداردهی اولیه انجام شد')
        return 'ستون Image ایجاد شد و مقداردهی اولیه انجام شد'

    except Exception as e:
        print(f'خطا: {e}')
        return f'خطا: {e}'

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
            
               
def create_sgroup_image_column():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # چک کنه که ستون Image وجود داره یا نه
        check_query = """
        SELECT 1 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'S_GROUP' AND COLUMN_NAME = 'Image'
        """
        cursor.execute(check_query)
        exists = cursor.fetchone()

        if exists:
            print("ستون Image از قبل در S_GROUP وجود دارد.")
            return "ستون Image از قبل در S_GROUP وجود دارد."

        # اضافه کردن ستون Image
        alter_query = "ALTER TABLE S_GROUP ADD Image NVARCHAR(255) NULL"
        cursor.execute(alter_query)

        # مقداردهی اولیه به همه رکوردها
        image_url = "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
        update_query = "UPDATE S_GROUP SET Image = ?"
        cursor.execute(update_query, (image_url,))

        conn.commit()

        print("ستون Image در S_GROUP با موفقیت ایجاد شد و مقداردهی اولیه انجام شد.")
        return "ستون Image در S_GROUP با موفقیت ایجاد شد و مقداردهی اولیه انجام شد."

    except Exception as e:
        print(f"خطا: {e}")
        return f"خطا: {e}"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def add_shomare_card_column():
    conn = get_article_connection()
    cursor = conn.cursor()

    table_name = "TblSetting_forooshgahi"
    column_name = "Shomare_Card"

    # بررسی اینکه آیا ستون وجود دارد
    cursor.execute("""
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """, (table_name, column_name))

    if not cursor.fetchone():
        # اگر ستون وجود نداشت، اضافه کن
        cursor.execute(f"""
        ALTER TABLE {table_name}
        ADD {column_name} NVARCHAR(20) NULL
        """)
        conn.commit()

    cursor.close()
    conn.close()

        

#ساخت جدول تعیین نوع تیپ قیمتی برای هر مشتری
def create_admin_settip_table():
    table_name = "admin_settip"
    conn = get_article_connection()
    cursor = conn.cursor()
    
    create_table_sql = f"""
    IF NOT EXISTS (
        SELECT * FROM sysobjects 
        WHERE name='{table_name}' AND xtype='U'
    )
    CREATE TABLE dbo.{table_name} (
        C_Code NVARCHAR(12),
        settip NVARCHAR(20)
    )
    """

    try:
        cursor.execute(create_table_sql)
        conn.commit()
        print(f"✅ Table '{table_name}' created successfully (if it did not exist).")
    except Exception as e:
        print(f"❌ Error creating table '{table_name}':", e)
    finally:
        cursor.close()
        conn.close()



def create_hidden_price_table():
    conn = get_article_connection()
    cursor = conn.cursor()

    # بررسی وجود جدول در دیتابیس
    cursor.execute("""
    SELECT 1
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'HiddenPrice'
    """)
    exists = cursor.fetchone()

    if not exists:
        # ایجاد جدول اگر وجود نداشت
        cursor.execute("""
        CREATE TABLE HiddenPrice (
        A_Code NVARCHAR(10) NOT NULL
        )
        """)
        conn.commit()

    cursor.close()
    conn.close()



def add_bit_column_to_settings():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        column_name = "HideNamojood"

        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'TblSetting_forooshgahi' AND COLUMN_NAME = ?
        """, column_name)

        if not cursor.fetchone():
            cursor.execute(f"""
                ALTER TABLE TblSetting_forooshgahi
                ADD {column_name} BIT DEFAULT 0
            """)
            conn.commit()

    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()



def add_bit_column_hidemojoodi_to_settings():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        column_name = "HideMojoodi"

        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'TblSetting_forooshgahi' AND COLUMN_NAME = ?
        """, column_name)

        if not cursor.fetchone():
            cursor.execute(f"""
                ALTER TABLE TblSetting_forooshgahi
                ADD {column_name} BIT DEFAULT 0
            """)
            conn.commit()

    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


#ساخت جدول امتیاز دادن برای یوزر   
def create_user_product_rate_table():
    conn = get_article_connection()
    cursor = conn.cursor()

    # بررسی وجود جدول و ایجاد آن در صورت نبودن
    cursor.execute("""
        IF OBJECT_ID('dbo.UserProductRate', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.UserProductRate (
                Id INT IDENTITY(1,1) PRIMARY KEY,
                UserToken NVARCHAR(255) NOT NULL,
                ProductA_Code NVARCHAR(50) NOT NULL
            )
        END
    """)

    conn.commit()
    cursor.close()
    conn.close()


#ساخت ستون توضیحات
def add_tozihat_column_if_not_exists():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود ستون Tozihat
        check_column_query = """
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Tozihat'
        """
        cursor.execute(check_column_query)
        column_exists = cursor.fetchone()[0]

        if column_exists == 0:
            # ایجاد ستون اگر وجود ندارد
            alter_table_query = "ALTER TABLE ARTICLE ADD Tozihat TEXT"
            cursor.execute(alter_table_query)
            conn.commit()
            print("ستون Tozihat با موفقیت اضافه شد.")
        else:
            print("ستون Tozihat از قبل وجود دارد.")

    except Exception as e:
        print("خطا در افزودن ستون Tozihat:", str(e))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# بررسی و ایجاد ستون 'Rate' در صورت نبودن
def ensure_article_rate_column(): 
    conn = get_article_connection()
    cursor = conn.cursor()

    check_rate_column_query = """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Rate'
        )
        BEGIN
            ALTER TABLE dbo.ARTICLE ADD Rate INT NULL
        END
    """
    cursor.execute(check_rate_column_query)

    conn.commit()
    cursor.close()
    conn.close()


 # بررسی و ایجاد ستون Av_Rate از نوع FLOAT با مقدار اولیه NULL
def ensure_article_av_rate_column():
    conn = get_article_connection()
    cursor = conn.cursor()

    check_and_add_av_rate_column = """
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Av_Rate'
    )
    BEGIN
        ALTER TABLE dbo.ARTICLE ADD Av_Rate FLOAT NULL
    END
    """
    cursor.execute(check_and_add_av_rate_column)

    conn.commit()
    cursor.close()
    conn.close()


#ساخت ستون تعداد دفعاتی که امتیازدهی شده
def ensure_article_rate_count_column():
    conn = get_article_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Rate_Count'
    """)
    exists = cursor.fetchone()[0]

    if not exists:
        cursor.execute("ALTER TABLE dbo.ARTICLE ADD Rate_Count INT NULL;")
        conn.commit()

    cursor.close()
    conn.close()


# بررسی و ایجاد ستون 'seen' در صورت نبودن
def ensure_article_seen_column():
    conn = get_article_connection()
    cursor = conn.cursor()
    check_seen_column_query = """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Seen'
        )
        BEGIN
            ALTER TABLE dbo.ARTICLE ADD Seen INT NULL
        END
    """
    cursor.execute(check_seen_column_query)
    conn.commit()
    cursor.close()
    conn.close()


#  بررسی و ایجاد ستون 'TedadKala' در صورت نبودن
def ensure_article_tedad_darkhasti_column():
    conn = get_article_connection()
    cursor = conn.cursor()
    check_tedadkala_column_query = """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'TedadDarkhasti'
        )
        BEGIN
            ALTER TABLE dbo.ARTICLE ADD TedadDarkhasti INT NOT NULL DEFAULT 0
        END
    """
    cursor.execute(check_tedadkala_column_query)
    conn.commit()
    cursor.close()
    conn.close()


#  بررسی و ایجاد ستون 'Eshantion' در صورت نبودن
def ensure_article_eshantion_column():
    conn = get_article_connection()
    cursor = conn.cursor()
    check_eshantion_column_query = """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Eshantion'
        )
        BEGIN
            ALTER TABLE dbo.ARTICLE ADD Eshantion NVARCHAR(255) NULL
        END
    """
    cursor.execute(check_eshantion_column_query)
    conn.commit()
    cursor.close()
    conn.close()
    
    
    
#ساخت ستون Image در ARTICLE
def add_image_column_with_default(default_image_url="https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"):
    conn = get_article_connection()
    cursor = conn.cursor()

    # 1. بررسی وجود ستون Image
    cursor.execute("""
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'Image'
    """)
    column_exists = cursor.fetchone()

    # 2. اگر ستون وجود نداشت، آن را اضافه کن
    if not column_exists:
        cursor.execute("""
            ALTER TABLE dbo.ARTICLE
            ADD Image NVARCHAR(255)
        """)
        conn.commit()
        print("ستون Image اضافه شد.")

    # 3. مقداردهی پیش‌فرض برای همه سطرها
    cursor.execute("""
        UPDATE dbo.ARTICLE
        SET Image = ?
        WHERE Image IS NULL
    """, default_image_url)
    conn.commit()

    print("مقداردهی ستون Image با آدرس اینترنتی انجام شد.")
    cursor.close()
    conn.close()
    
    

#ساخت جدولی که در متد /assign_gift نامش مشخص شده و اشانتیون ها با مشتقاتش داخل اون ذخیره میشه
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
    
    
    
# تابع تبدیل کلمات عربی موجود در ستون به فارسی
def normalize_to_persian(text):
    if not text:
        return ''
    replacements = {
        '\u064A': 'ی',  # ي
        '\u0649': 'ی',  # ى
        '\u06CC': 'ی',  # ی (فارسی)
        '\u0643': 'ک',  # ك
        '\u06A9': 'ک',  # ک (فارسی)
        '\u0629': 'ه',  # ة
        '\u0624': 'و',  # ؤ
        '\u0623': 'ا',  # أ
        '\u0625': 'ا',  # إ
        '\u0626': 'ی',  # ئ
        '\u0671': 'ا',  # ٱ
        '\u200C': '',   # ZWNJ
        '\u200F': '',   # RTL mark
        '\u061C': '',   # Arabic Letter Mark
        '\uFEFF': '',   # BOM
    }
    return ''.join(replacements.get(c, c) for c in text)



# ساخت و پر کردن ستون convert_persian
def create_and_fill_convert_persian_column():
    conn = get_article_connection()
    cursor = conn.cursor()

    # ساخت ستون اگر وجود نداشت
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'convert_persian'
        )
        BEGIN
            ALTER TABLE dbo.ARTICLE ADD convert_persian NVARCHAR(255) NULL
        END
    """)
    conn.commit()

    # خواندن اطلاعات از A_Name
    cursor.execute("SELECT A_Code, A_Name FROM dbo.ARTICLE")
    rows = cursor.fetchall()

    for a_code, a_name in rows:
        normalized = normalize_to_persian(a_name or '')
        cursor.execute("""
            UPDATE dbo.ARTICLE 
            SET convert_persian = ? 
            WHERE A_Code = ?
        """, (normalized, a_code))

    conn.commit()
    cursor.close()
    conn.close()
    

#use in /search_customers   
# اضافه شدن ستون customer_persian برای تبدیل نام عربی مشتریان به فارسی
def update_customer_persian_column():
    conn = get_article_connection()  # از همان اتصال برای Holoo1 استفاده می‌کنیم
    cursor = conn.cursor()

    # 1. اگر ستون وجود نداشت، ایجادش کن
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'CUSTOMER' AND COLUMN_NAME = 'customer_persian'
        )
        BEGIN
            ALTER TABLE dbo.CUSTOMER ADD customer_persian NVARCHAR(255) NULL
        END
    """)
    conn.commit()

    # 2. خواندن داده‌ها از C_Name
    cursor.execute("SELECT C_Code, C_Name FROM dbo.CUSTOMER")
    rows = cursor.fetchall()

    # 3. تعریف جایگزینی حروف عربی با فارسی
    replacements = {
        'ي': 'ی',
        'ى': 'ی',
        'ك': 'ک',
        'ة': 'ه',
        '\u200C': '',
        '\u200F': '',
        '\u061C': '',
        '\uFEFF': '',
    }

    for c_code, c_name in rows:
        if not c_name:
            continue

        fixed = c_name
        for arabic, persian in replacements.items():
            fixed = fixed.replace(arabic, persian)

        # 4. نوشتن مقدار اصلاح‌شده در ستون جدید
        cursor.execute("""
            UPDATE dbo.CUSTOMER
            SET customer_persian = ?
            WHERE C_Code = ?
        """, (fixed, c_code))

    conn.commit()
    cursor.close()
    conn.close()



def get_full_customer_data(c_code, show_mandeh):
    conn = get_article_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            C.C_Code, C.C_Name, C.C_Mobile, C.C_Address,
            C.C_Tel, C.C_Code_C, C.Etebar, C.City_Code,
            C.InListSiah, CI.Name AS City_Name,
            W.Mandeh, W.National_Code
        FROM CUSTOMER C
        LEFT JOIN CITY CI ON CI.City_Code = C.City_Code
        LEFT JOIN dbo.W_Calc_Mandeh_Customer W ON W.C_Code = C.C_Code
        WHERE C.C_Code = ?
    """, (c_code,))
    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    if not customer:
        return None

    mandeh_value = (
        str(customer.Mandeh or 0) if show_mandeh == 1
        else "شما مجاز به دیدن این قسمت نیستید"
    )

    return {
        "FldN_City": customer.City_Name,
        "FldC_Ashkhas": customer.C_Code,
        "FldC_Ashkhas_C": customer.C_Code_C or "0",
        "FldAddress": customer.C_Address or "",
        "FldMob": customer.C_Mobile,
        "FldTell": customer.C_Tel,
        "FldEtebar": str(customer.Etebar or "0"),
        "FldN_Ashkhas": customer.C_Name,
        "FldC_City": str(customer.City_Code),
        "FldVaziat": "بد حساب" if customer.InListSiah else "خوش حساب",
        "FldMandeHesab": mandeh_value,
        "FldNationalCode": customer.National_Code or "",
        "FldTakhfifVizhe": "0",
        "FldC_Visitor": "0",
        "FldTipFee": "0",
        "FldLat": "0",
        "FldLon": "0",
    }


#ساختن ستون لاگین در جدول کاستومرز
def create_customer_login_column():
    """
    ستون Login (BIT DEFAULT 0) را در جدول CUSTOMER ایجاد می‌کند
    اگر از قبل وجود داشته باشد، هیچ تغییری انجام نمی‌دهد.
    """
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # آیا ستون Login وجود دارد؟
        cursor.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'CUSTOMER' AND COLUMN_NAME = 'Login'
        """)
        already_exists = cursor.fetchone()

        if already_exists:
            print("ستون Login قبلاً در جدول CUSTOMER وجود دارد.")
            return "ستون Login قبلاً وجود دارد."

        # ایجاد ستون Login با مقدار پیش‌فرض 0
        cursor.execute("""
            ALTER TABLE CUSTOMER
            ADD Login BIT NOT NULL DEFAULT 0
        """)
        conn.commit()
        print("ستون Login با موفقیت ایجاد شد.")
        return "ستون Login با موفقیت ایجاد شد."

    except Exception as e:
        print(f"خطا در ایجاد ستون Login: {e}")
        return f"خطا: {e}"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



#درست کردن ستون امتیاز ادمین در ARTICLE
def ensure_admin_rate_column_exists():
    conn = get_article_connection()
    cursor = conn.cursor()

    try:
        # Check if the column 'admin_rate' exists in 'ARTICLE' table
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ARTICLE' AND COLUMN_NAME = 'admin_rate'
        """)
        column_exists = cursor.fetchone()

        # If the column does not exist, add it
        if not column_exists:
            cursor.execute("""
                ALTER TABLE dbo.ARTICLE
                ADD admin_rate INT NULL
            """)
            conn.commit()
            print("The 'admin_rate' column has been successfully added.")
        else:
            print("The 'admin_rate' column already exists.")
    except Exception as e:
        print(f"Error checking or adding 'admin_rate' column: {e}")
    finally:
        cursor.close()
        conn.close()
        
        

def create_login_forooshgahi_table():
    conn = get_article_connection()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'LoginForooshgahi'
        )
        BEGIN
            CREATE TABLE LoginForooshgahi (
                C_Mobile NVARCHAR(20),
                CodeVorood NVARCHAR(20),
                RequestTime DATETIME,
                Ok BIT
            )
        END
    """)

    conn.commit()
    cursor.close()
    conn.close()
    


@holoo_bp.route("/register", methods=["POST"])
@require_api_key
def add_customer():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()
        if cursor is None:
            return jsonify({"error": "Database connection is not available."}), 500
        # بررسی و افزودن ستون 'webcom' اگر وجود نداشت
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
        region = data.get("region") # Cust_Ostan
        city = data.get("city") # Cust_City
        # حذف بررسی visitor_code
        if not phone_number or not full_name:
            return (
                jsonify({"error": "phoneNumber و fullName الزامی هستند"}), 400
            )
        cursor.execute(
            "SELECT * FROM CUSTOMER WHERE C_Mobile = ? OR C_Name = ?",
            (phone_number, full_name),
        )
        existing_customer = cursor.fetchone()
        if existing_customer:
            return (
                jsonify({"message": "مشتری با این شماره یا نام قبلاً ثبت شده است."}),
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
                1, # مقدار webcom
            ),
        )
        conn.commit()
        return jsonify({"message": "مشتری با موفقیت ثبت شد", "C_Code": new_c_code}), 201
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500



# -----------------------------
# لاگین و گرفتن apikey


@holoo_bp.route("/get-user-conn", methods=["POST"])
def get_user_conn_info():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn1 = conn2 = None
    try:
        # مرحله 1: گرفتن ApiKey
        conn1 = get_main_db_connection1()
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
        conn2 = get_second_db_connection1()
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

    
    

from datetime import datetime

@holoo_bp.route('/login', methods=["POST", "GET"])
def login():
    import traceback
    import random
    from datetime import datetime
    import requests

    def send_sms(mobile, code_vorood):
        url = "https://api2.ippanel.com/api/v1/sms/pattern/normal/send"
        headers = {
            "apikey": "OWYyOGU3MTUtYzAyZi00ZDg3LTlhOTUtNDdmZDNiYTA2NGUyNGVhM2ViYWNiODZiYTY1M2E0MGU5M2RkYTg4ZTNhYzA=",
            "Content-Type": "application/json"
        }
        data = {
            "code": "fs3hncvdgpy7fo7",
            "sender": "+983000505",
            "recipient": mobile,
            "variable": {"verification-code": code_vorood}
        }
        try:
            resp = requests.post(url, json=data, headers=headers)
            if resp.status_code != 200:
                print(f"SMS ارسال نشد. کد وضعیت: {resp.status_code}, پاسخ: {resp.text}")
        except Exception as e:
            print(f"خطا در ارسال پیامک: {e}")

    try:
        if request.method == "GET":
            with get_article_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT FldTaiidAdmin FROM TblSetting_forooshgahi")
                setting_row = cursor.fetchone()
                fld_taiid_admin = setting_row[0] if setting_row else 0

                if fld_taiid_admin != 1:
                    return jsonify({
                        "status": "ok",
                        "FldTaiidAdmin": False,
                        "message": "تأیید ادمین غیرفعال است."
                    })

                cursor.execute("""
                    SELECT L.C_Mobile, C.C_Name, L.RequestTime
                    FROM LoginForooshgahi L
                    INNER JOIN CUSTOMER C ON L.C_Mobile = C.C_Mobile
                    WHERE (L.Ok = 0 OR L.Ok IS NULL)
                    AND L.CodeVorood IS NOT NULL
                """)
                users = [
                    {
                        "C_Mobile": row[0],
                        "C_Name": row[1],
                        "RequestTime": row[2].strftime("%Y-%m-%d %H:%M:%S") if row[2] else None
                    }
                    for row in cursor.fetchall()
                ]

                return jsonify({
                    "status": "ok",
                    "FldTaiidAdmin": True,
                    "pending_users": users
                })

        # ---------- POST ----------
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "داده‌ای دریافت نشد."}), 400

        mobile = data.get('mobile')
        code = data.get('code')

        if not mobile:
            return jsonify({"status": "error", "message": "شماره موبایل الزامی است."}), 400

        with get_article_connection() as conn:
            cursor = conn.cursor()

            if code:
                cursor.execute("SELECT FldTaiidAdmin FROM TblSetting_forooshgahi")
                fld_taiid_admin = cursor.fetchone()[0] if cursor.fetchone() else 0

                if fld_taiid_admin == 1:
                    cursor.execute("SELECT Ok FROM LoginForooshgahi WHERE C_Mobile = ?", (mobile,))
                    ok_row = cursor.fetchone()
                    if not ok_row or ok_row[0] != 1:
                        return jsonify({
                            "status": "error",
                            "message": "برای ورود نیاز به تأیید درخواست توسط ادمین دارید."
                        }), 403

                cursor.execute("SELECT CodeVorood FROM LoginForooshgahi WHERE C_Mobile = ?", (mobile,))
                row = cursor.fetchone()
                if not row or row[0] != code:
                    return jsonify({"status": "error", "message": "کد وارد شده صحیح نیست."}), 401

                # ادامه مراحل ورود (واکشی فروشگاه و C_Code)
                # ...
                # return jsonify({...})

            # مرحله اول: ارسال کد ورود
            cursor.execute("SELECT C_Mobile FROM CUSTOMER WHERE C_Mobile = ?", (mobile,))
            if not cursor.fetchone():
                return jsonify({"status": "error", "message": "شماره موبایل در سیستم ثبت نشده است"}), 400

            code_vorood = str(random.randint(1000, 9999))
            request_time = datetime.now()

            cursor.execute("SELECT C_Mobile FROM LoginForooshgahi WHERE C_Mobile = ?", (mobile,))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE LoginForooshgahi SET CodeVorood=?, RequestTime=? WHERE C_Mobile=?
                """, (code_vorood, request_time, mobile))
            else:
                cursor.execute("""
                    INSERT INTO LoginForooshgahi (C_Mobile, CodeVorood, RequestTime) VALUES (?, ?, ?)
                """, (mobile, code_vorood, request_time))
            conn.commit()

            send_sms(mobile, code_vorood)
            return jsonify({"status": "ok", "message": "کد ورود ارسال شد", "code": code_vorood})

    except Exception:
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": "خطای داخلی سرور"}), 500



@holoo_bp.route('/accept', methods=['GET', 'POST'])
@require_api_key
def accept():
    if request.method == 'GET':
        try:
            conn = get_article_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT C_Mobile FROM LoginForooshgahi")
            mobiles = [row.C_Mobile for row in cursor.fetchall()]
            cursor.close()
            conn.close()

            return jsonify({"mobiles": mobiles})
        except Exception as e:
            return jsonify({"status": "error", "message": f"خطا در دریافت شماره‌ها: {str(e)}"}), 500

    elif request.method == 'POST':
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "داده‌ای دریافت نشد."}), 400

        mobile = data.get("mobile")
        ok_value = data.get("ok")

        # بررسی مقدار ok
        if str(ok_value) not in ["0", "1"]:
            return jsonify({"status": "error", "message": "مقدار ok فقط می‌تواند 0 یا 1 باشد."}), 400

        try:
            conn = get_article_connection()
            cursor = conn.cursor()

            # بررسی وجود موبایل
            cursor.execute("SELECT COUNT(*) FROM LoginForooshgahi WHERE C_Mobile = ?", (mobile,))
            result = cursor.fetchone()

            if result[0] == 0:
                cursor.close()
                conn.close()
                return jsonify({"status": "error", "message": "شماره موبایل شما موجود نیست، ابتدا ثبت‌نام کنید."}), 404

            # به‌روزرسانی مقدار ok
            cursor.execute("UPDATE LoginForooshgahi SET Ok = ? WHERE C_Mobile = ?", (int(ok_value), mobile))
            conn.commit()

            cursor.close()
            conn.close()

            return jsonify({"status": "ok", "message": f"مقدار ok با موفقیت برای شماره {mobile} ذخیره شد."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"خطا در ذخیره‌سازی: {str(e)}"}), 500



def make_image_url(article_code):
    base_url = request.host_url.rstrip("/")
    if article_code:
        encoded_code = urllib.parse.quote(article_code)
        url = f"{base_url}/get_image_by_code?code={encoded_code}"
    else:
        url = f"{base_url}/get_image_by_code?default=1"
    print("IMAGE URL:", url)  # برای دیباگ
    return url



def get_vahedpool(cursor) -> str:
    """
    خواندن واحد پول از تنظیمات فروشگاهی و برگرداندن 'toman' یا 'rial'
    """
    try:
        cursor.execute("SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
        row = cursor.fetchone()
        if row and row[0] and row[0].strip().lower() == "toman":
            return "toman"
    except:
        pass
    return "rial"



@holoo_bp.route("/Get_Holoo_Articles", methods=["GET", "POST"])
@require_api_key
def get_holoo_articles():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()
        
        # خواندن واحد پول (rial یا toman)
        cursor.execute("SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
        pool_row = cursor.fetchone()
        vahedpool_raw = pool_row[0] if pool_row and pool_row[0] else "rial"
        is_toman = vahedpool_raw.strip().lower() == "toman"
        
        # خواندن مقدار HideMojoodi و HideNamojood از تنظیمات
        cursor.execute("SELECT HideMojoodi, HideNamojood FROM TblSetting_forooshgahi")
        setting_row = cursor.fetchone()
        hide_mojoodi = bool(setting_row[0]) if setting_row and setting_row[0] is not None else False
        hide_zero_exist = bool(setting_row[1]) if setting_row and setting_row[1] is not None else False


        # دریافت لیست کالاهایی که قیمت‌شان مخفی است
        cursor.execute("SELECT A_Code FROM HiddenPrice")
        hidden_price_codes = {row[0] for row in cursor.fetchall()}

        if request.method == "POST":
            data = request.get_json(force=True)
        else:
            data = request.args

        page = str(data.get("page", "1")).strip()
        only_all = page.lower() == "all" and not data.get("visitor_id")
        per_page = int(data.get("per_page", 10)) if not only_all else None

        visitor_id = data.get("visitor_id")
        price_type = int(data.get("price_type", 1)) if not only_all else 1
        hidden_only = data.get("hidden_only", "false").lower() == "true"
        custom_prices = {}
        if request.method == "POST" and request.is_json:
            custom_prices = request.get_json().get("custom_prices", {})

        # تنظیمات پیش‌فرض
        show_all_prices = False
        show_end_buy_price = False
        can_enter_fee = False
        show_gifts = False

        if visitor_id:
            cursor.execute("""
                SELECT WSetTip, [ShowEndBuyPrice], WEnterFee, WSetEshan
                FROM TblSetting_Visitori
                WHERE FldC_Visitor = ?
            """, (visitor_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "کد ویزیتور نامعتبر است."}), 404
            show_all_prices = bool(row[0])
            show_end_buy_price = bool(row[1])
            can_enter_fee = bool(row[2])
            show_gifts = bool(row[3])
            if price_type > 1 and not show_all_prices:
                return jsonify({"error": "دسترسی مشاهده قیمت تیپ برای این ویزیتور وجود ندارد."}), 403

        # شرایط فیلتر کالاها
        base_conditions = """
            a.A_Code IS NOT NULL AND a.A_Name IS NOT NULL AND a.Sel_Price IS NOT NULL 
            AND a.Sel_Price > 0 AND a.IsActive = 1
        """
        if hide_zero_exist:
            base_conditions += " AND a.Exist > 0"

        # محاسبه تعداد کل کالاها
        if hidden_only:
            count_query = f"""
                SELECT COUNT(*)
                FROM article a
                WHERE a.A_Code IN (SELECT A_Code FROM HiddenPrice) AND {base_conditions}
            """
        else:
            count_query = f"""
                SELECT COUNT(*)
                FROM article a
                WHERE {base_conditions}
            """
        cursor.execute(count_query)
        total_articles = cursor.fetchone()[0]

        # دریافت کالاها (all)
        if only_all:
            cursor.execute(f"""
                SELECT a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist, a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,
                       a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5, a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                       a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton, a.Tozihat, p.PicturePath
                FROM article a
                LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                WHERE {base_conditions}
                ORDER BY a.A_Name ASC
            """)
            articles = cursor.fetchall()

        # دریافت کالاهای مخفی
        elif hidden_only:
            cursor.execute(f"""
                SELECT a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist, a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,
                       a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5, a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                       a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton, a.Tozihat, p.PicturePath
                FROM article a
                LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                WHERE a.A_Code IN (SELECT A_Code FROM HiddenPrice) AND {base_conditions}
                ORDER BY a.A_Name ASC
            """)
            articles = cursor.fetchall()

        # صفحه‌بندی
        else:
            page_int = int(page)
            offset = (page_int - 1) * per_page
            start_row = offset + 1
            end_row = offset + per_page
            cursor.execute(f"""
                WITH OrderedArticles AS (
                    SELECT
                        a.A_Code, a.A_Code_C, a.A_Name, a.Sel_Price, a.VahedCode, a.Exist, a.Attribute, a.DarsadTakhfif, a.PriceTakhfif,
                        a.Sel_Price2, a.Sel_Price3, a.Sel_Price4, a.Sel_Price5, a.Sel_Price6, a.Sel_Price7, a.Sel_Price8, a.Sel_Price9, a.Sel_Price10,
                        a.EndBuy_Price, a.A_Max, a.A_Min, a.Karton, a.Tozihat, p.PicturePath,
                        ROW_NUMBER() OVER (ORDER BY a.A_Name ASC) AS RowNum
                    FROM article a
                    LEFT JOIN HLOPictures p ON a.A_Code = p.Code
                    WHERE {base_conditions}
                )
                SELECT * FROM OrderedArticles
                WHERE RowNum BETWEEN ? AND ?
                ORDER BY RowNum
            """, (start_row, end_row))
            articles = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]

        # واحدها
        cursor.execute("SELECT Unit_Code, Unit_Name, Unit_Few, Vahed_Vazn FROM UNIT")
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
            
            # اگر واحد تومان باشد، قیمت‌ها تقسیم بر 10 شوند
            if is_toman:
                sel_price /= 10
                takhfif_final /= 10

            article_data = {
                "FldC_Kala": article_code,
                "FldACode_C": row_dict.get("A_Code_C"),
                "FldN_Kala": row_dict.get("A_Name"),
                "FldFee": sel_price,
                "FldFeeBadAzTakhfif": takhfif_final,
                "FldMande": "تماس بگیرید" if hide_mojoodi else exist,
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
            }
            
            
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
                SELECT Gift_ID, A_Code, A_Code_C, A_Name, Model, Buy_Price, Gift_Code, is_gift, Created_At
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
                f"""
                SELECT COUNT(*) FROM article a
                WHERE {base_conditions}
                """
            )
            total_count = cursor.fetchone()[0]


        result = {
            "articles": article_list,
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



def output_path(relative_path):
    """مسیر ذخیره‌سازی کنار فایل اجرایی یا مسیر اصلی پروژه"""
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


#تابع دریافت URL عکس از گوگل (محدود به سایت digikala.com)
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





def fetch_best_image_url(query: str, timeout=30) -> str | None:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import urllib.parse

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # اگر نمی‌خوای پنجره باز بشه
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")

    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        try:
            driver.get(search_url)
            wait = WebDriverWait(driver, timeout)

            # پذیرش کوکی (اختیاری)
            try:
                accept_button_xpath = "//button[.//div[contains(text(), 'پذیرفتن همه')]]"
                accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, accept_button_xpath)))
                accept_button.click()
            except TimeoutException:
                pass

            thumbnails = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.H8Rx8c")))
            thumbnails[0].click()
            time.sleep(2)  # صبر برای لود تصویر

            img_selectors = ["img.n3VNCb", "img.r48jcc", "img.sFlh5c"]
            best_url = None
            max_area = 0

            for _ in range(10):
                for selector in img_selectors:
                    images = driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in images:
                        src = img.get_attribute("src")
                        if src and src.startswith("http"):
                            try:
                                width = driver.execute_script("return arguments[0].naturalWidth;", img)
                                height = driver.execute_script("return arguments[0].naturalHeight;", img)
                            except:
                                width = img.size.get('width', 0)
                                height = img.size.get('height', 0)
                            area = width * height
                            if area > max_area:
                                max_area = area
                                best_url = src
                time.sleep(1)

            return best_url

        except Exception as e:
            print(f"Error fetching image URL: {e}")
            return None


def fetch_image_url(name: str) -> str | None:
    return fetch_best_image_url(name)



@holoo_bp.route("/get_images_by_codes", methods=["POST", "OPTIONS"])
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
        with closing(get_article_connection()) as conn:
            cursor = conn.cursor()

            # پردازش item_names_only
            for item in item_names_only:
                code = item.get("code")
                name = item.get("name")
                try:
                    img_url = fetch_best_image_url(name)
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
                cursor.execute("SELECT A_Name FROM Article WHERE A_Code = ?", (code,))
                row = cursor.fetchone()

                name = item_names_dict.get(code)
                if not name:
                    name = row[0] if row and row[0] else None

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
                    img_url = fetch_best_image_url(name)
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
                                    image.save(save_path, format="JPEG", quality=95)
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


@holoo_bp.route("/get_image_by_code")
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
        conn = get_article_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT PicturePath, image_src FROM [HLOPictures] WHERE Code = ?", (code,)
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




@holoo_bp.route("/get_image")
@require_api_key
def get_image():
    path = request.args.get("path")
    if not path:
        return redirect(
            "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
        )

    try:
        path = urllib.parse.unquote(path)
        if not os.path.exists(path):
            return redirect(
                "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
            )
        return send_file(path)
    except Exception as e:
        print(f"Error serving file: {e}")
        return redirect(
            "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"
        )
            


def create_gift_table_if_not_exists():
    table_name = "MyGift_WC"
    conn = get_article_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            IF NOT EXISTS (
                SELECT * FROM sysobjects WHERE name='{table_name}' AND xtype='U'
            )
            CREATE TABLE dbo.{table_name} (
                Gift_ID INT IDENTITY(1,1) PRIMARY KEY,
                A_Code NVARCHAR(50),
                A_Code_C NVARCHAR(50),
                A_Name NVARCHAR(255),
                Model NVARCHAR(100),
                Buy_Price DECIMAL(18,2),
                Gift_Code NVARCHAR(50),
                is_gift BIT,
                Created_At DATETIME,
                Quantity INT,
                Threshold INT
            )
        """)
        conn.commit()
        print(f"✅ Table '{table_name}' created or already exists.")
    except Exception as e:
        print(f"❌ Error creating table '{table_name}':", e)
    finally:
        cursor.close()
        conn.close()



@holoo_bp.route("/assign_gift", methods=["GET", "POST"])
@require_api_key
def assign_gift_if_eligible():
    fixed_table_name = "MyGift_WC"
    if request.method == "GET":
        conn = get_article_connection()
        ensure_wc_table_exists(conn, fixed_table_name)
        cursor = conn.cursor()
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
    # POST
    data = request.get_json()
    required_fields = ["A_Code", "quantity", "gift_code", "threshold"]
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return (
            jsonify(
                {"error": "Missing required fields", "missing_fields": missing_fields}
            ),
            400,
        )
    a_code = data["A_Code"]
    quantity = int(data["quantity"])
    gift_code = data["gift_code"]
    threshold = int(data["threshold"])
    # محاسبه تعداد هدیه
    gift_count = quantity // threshold
    if gift_count < 1:
        return (
            jsonify({"error": "Not eligible for gift: quantity below threshold"}),
            400,
        )
    conn = get_article_connection()
    ensure_wc_table_exists(conn, fixed_table_name)
    cursor = conn.cursor()
    # دریافت اطلاعات کالا برای هدیه
    cursor.execute(
        """
        SELECT TOP 1 [A_Code], [A_Code_C], [A_Name], [Model], [Buy_Price]
        FROM [dbo].[Article]
        WHERE [A_Code] = ?
    """,
        gift_code,
    )
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "Gift product not found"}), 404
    created_at = datetime.utcnow()
    # درج gift_count ردیف در جدول
    for _ in range(gift_count):
        cursor.execute(
            f"""
            INSERT INTO dbo.{fixed_table_name}
            ([A_Code], [A_Code_C], [A_Name], [Model], [Buy_Price],
             [Gift_Code], [is_gift], [Created_At], [Quantity], [Threshold])
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            a_code,
            row.A_Code_C,
            row.A_Name,
            row.Model,
            row.Buy_Price,
            gift_code,
            1,
            created_at,
            quantity,
            threshold,
        )
    conn.commit()
    cursor.close()
    conn.close()
    return (
        jsonify(
            {
                "message": f"{gift_count} gift(s) assigned successfully to table '{fixed_table_name}'",
                "gift_count": gift_count,
                "quantity": quantity,
                "threshold": threshold,
                "gift_code": gift_code,
                "gift_name": row.A_Name,
                "model": row.Model,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        ),
        200,
    )
    
    

@holoo_bp.route("/delete_gift", methods=["POST"])
@require_api_key
def delete_gift():
    data = request.get_json()
    gift_code = data.get("gift_code")
    a_code = data.get("A_Code")
    if not gift_code or not a_code:
        return jsonify({"error": "Fields 'A_Code' and 'gift_code' are required"}), 400
    conn = get_article_connection()
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


# نمایش لیست همه مشتریان به همراه اطلاعاتشان بوسیله کلید مشتریان که در صفحه خانه هلو موجود میباشد
@holoo_bp.route('/send_customers_Visitory', methods=['GET', 'POST'])
@require_api_key
def send_customers():
    if request.method == 'POST':
        c_code = request.form.get('C_Code') or (request.get_json() or {}).get('C_Code')
        if c_code:
            return search_customer(c_code)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    conn = get_article_connection()
    cursor = conn.cursor()

    # دریافت تمام مشتری‌ها حتی اگر موبایل یا شهر یا ... نداشته باشند
    cursor.execute("""
        SELECT 
            CUSTOMER.C_Mobile, CUSTOMER.C_Name, CUSTOMER.C_Code, CUSTOMER.C_Address,
            CUSTOMER.C_Tel, CUSTOMER.C_Code_C, CUSTOMER.Etebar, CUSTOMER.City_Code,
            CUSTOMER.InListSiah, CITY.Name as City_Name
        FROM CUSTOMER
        LEFT JOIN CITY ON CITY.City_Code = CUSTOMER.City_Code
    """)
    all_customers = cursor.fetchall()

    total_customers = len(all_customers)
    total_pages = math.ceil(total_customers / per_page)

    start = (page - 1) * per_page
    end = start + per_page
    customers_page = all_customers[start:end]
    c_codes_in_page = [cust.C_Code for cust in customers_page]
    
    format_strings = ','.join(['?'] * len(c_codes_in_page))
    cursor.execute(f"""
        SELECT Common, Mandeh 
        FROM SARFASL 
        WHERE Common IN ({format_strings})
    """, c_codes_in_page)


    mandeh_dict = {row.Common: row.Mandeh if row.Mandeh is not None else 0 for row in cursor.fetchall()}



    new_customers = []
    for customer in customers_page:
        new_customers.append({
            "FldN_City": customer.City_Name or "",
            "FldC_Ashkhas": customer.C_Code or "",
            "FldC_Ashkhas_C": customer.C_Code_C or "0",
            "FldAddress": customer.C_Address or "",
            "FldMob": customer.C_Mobile or "",
            "FldTell": customer.C_Tel or "",
            "FldEtebar": str(customer.Etebar or "0"),
            "FldN_Ashkhas": customer.C_Name or "",
            "FldC_City": str(customer.City_Code) if customer.City_Code is not None else "0",
            "FldVaziat": "بد حساب" if customer.InListSiah else "خوش حساب",
            "FldMandeHesab": str(mandeh_dict.get(customer.C_Code, 0)),
            "FldTakhfifVizhe": "0",
            "FldC_Visitor": "0",
            "FldTipFee": "0",
            "FldLat": "0",
            "FldLon": "0",
        })

    cursor.close()
    conn.close()

    response_data = {
        "customers": new_customers,
        "pagination": {
            "current_page": page,
            "per_page": per_page,
            "total_customers": total_customers,
            "total_pages": total_pages
        }
    }

    return Response(json.dumps(response_data, ensure_ascii=False), content_type='application/json; charset=utf-8')




@holoo_bp.route('/search_keyword', methods=['POST'])
@require_api_key
def search_keyword():
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "درخواست باید از نوع JSON باشد."
        }), 400

    data = request.get_json()
    a_name = data.get('a_name', '').strip()

    if not a_name:
        return jsonify({
            "status": "error",
            "message": "کلمه جستجو وارد نشده است."
        }), 400

    normalized_a_name = a_name.replace(' ', '')

    conn = get_article_connection()
    cursor = conn.cursor()
    
    # دریافت واحد پول از جدول تنظیمات
    cursor.execute("SELECT TOP 1 FldVahedpool FROM dbo.TblSetting_forooshgahi")
    row_vahedpool = cursor.fetchone()
    vahedpool = row_vahedpool[0].lower() if row_vahedpool and row_vahedpool[0] else 'rial'


    # واکشی لیست کالاهایی که نامشان شبیه عبارت جستجو است
    cursor.execute("""
        SELECT A_Code, A_Code_C, A_Name, Sel_Price, VahedCode, Exist, Attribute, DarsadTakhfif, PriceTakhfif,
               Sel_Price2, Sel_Price3, Sel_Price4, Sel_Price5, Sel_Price6, Sel_Price7, Sel_Price8, Sel_Price9, Sel_Price10,
               EndBuy_Price, A_Max, A_Min, Karton, Image, Seen, Rate_Count, Av_Rate
        FROM dbo.ARTICLE
        WHERE REPLACE(convert_persian, ' ', '') LIKE ?
          AND A_Code IS NOT NULL
          AND A_Name IS NOT NULL
          AND Sel_Price IS NOT NULL
          AND Sel_Price > 0
          AND IsActive = 1
    """, (f'%{normalized_a_name}%',))
    articles = cursor.fetchall()

    # دریافت لیست واحدها
    cursor.execute("SELECT Unit_Code, Unit_Name FROM dbo.UNIT")
    units = {row[0]: row[1] for row in cursor.fetchall()}

    # دریافت لیست کد کالاهایی که هدیه شده‌اند
    cursor.execute("""
        SELECT Gift_Code
        FROM dbo.MyGift_WC
        WHERE is_gift = 1 AND Gift_Code IS NOT NULL
    """)
    gifted_codes = {row[0] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    if not articles:
        return jsonify({
            "status": "not_found",
            "message": "محصولی با این نام یافت نشد."
        }), 404

    results = []
    for row in articles:
        is_gifted = row[0] in gifted_codes
        vahed_name = units.get(row[4], "نامشخص")
        try:
            sel_price = float(row[3]) if row[3] not in [None, ""] else 0
            darsad_takhfif = float(row[7]) if row[7] not in [None, ""] else 0
            price_takhfif = float(row[8]) if row[8] not in [None, ""] else 0
        except ValueError:
            sel_price, darsad_takhfif, price_takhfif = 0, 0, 0

        if darsad_takhfif > 0:
            takhfifnahayi = sel_price - ((sel_price * darsad_takhfif) / 100)
        elif price_takhfif > 0:
            takhfifnahayi = sel_price - price_takhfif
        else:
            takhfifnahayi = sel_price
        
        # اگر واحد پول تومان باشد، مقادیر قیمتی را تقسیم بر 10 کن
        if vahedpool == 'toman':
            sel_price /= 10
            takhfifnahayi /= 10
            row = list(row)
            for i in range(9, 18):  # Sel_Price2 تا Sel_Price10
                row[i] = float(row[i]) / 10 if row[i] not in [None, ""] else 0
            row[18] = float(row[18]) / 10 if row[18] not in [None, ""] else 0  # EndBuyPrice


        results.append({
            "FldC_Kala": row[0],
            "FldACode_C": row[1],
            "FldN_Kala": row[2],
            "FldFee": sel_price,
            "FldMande": int(row[5]) if row[5] not in [None, ""] else 0,
            "FldN_Vahed": vahed_name,
            "FldTozihat": row[6] if row[6] else "",
            "FldFeeBadAzTakhfif": takhfifnahayi,
            "Sel_Price2": float(row[9]) if row[9] not in [None, ""] else 0,
            "Sel_Price3": float(row[10]) if row[10] not in [None, ""] else 0,
            "Sel_Price4": float(row[11]) if row[11] not in [None, ""] else 0,
            "Sel_Price5": float(row[12]) if row[12] not in [None, ""] else 0,
            "Sel_Price6": float(row[13]) if row[13] not in [None, ""] else 0,
            "Sel_Price7": float(row[14]) if row[14] not in [None, ""] else 0,
            "Sel_Price8": float(row[15]) if row[15] not in [None, ""] else 0,
            "Sel_Price9": float(row[16]) if row[16] not in [None, ""] else 0,
            "Sel_Price10": float(row[17]) if row[17] not in [None, ""] else 0,
            "EndBuyPrice": float(row[18]) if row[18] not in [None, ""] else 0,
            "FldMax": float(row[19]) if row[19] not in [None, ""] else 0,
            "FldMin": float(row[20]) if row[20] not in [None, ""] else 0,
            "FldTedadKarton": int(row[21]) if row[21] not in [None, ""] else 0,
            "FldImage": row[22] if row[22] else "",
            "Seen": int(row[23]) if row[23] not in [None, ""] else 0,
            "RateCount": int(row[24]) if row[24] not in [None, ""] else 0,
            "AvRate": float(row[25]) if row[25] not in [None, ""] else 0,
            "IsGifted": is_gifted
        })

    return jsonify({
        "status": "success",
        "a_name": a_name,
        "no_results": False,
        "results": results
    }), 200



@holoo_bp.route('/search_customer', methods=['POST'])
@require_api_key
def search_customer():
    data = request.get_json()
    if not data or 'cname' not in data:
        return jsonify({"status": "error", "message": "عبارت جستجو وارد نشده است."}), 400

    keyword = data['cname'].strip()
    if not keyword:
        return jsonify({"status": "error", "message": "عبارت جستجو وارد نشده است."}), 400

    normalized_keyword = keyword.replace(' ', '')

    conn = get_article_connection()
    cursor = conn.cursor()
    
    # گرفتن page و per_page با مقدار پیش‌فرض
    try:
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 10))
    except ValueError:
        return jsonify({"status": "error", "message": "مقادیر صفحه و تعداد آیتم نامعتبر هستند."}), 400


    # خواندن مجوز نمایش مانده حساب
    try:
        cursor.execute("SELECT TOP 1 WMandeHesab FROM TblSetting_forooshgahi")
        row = cursor.fetchone()
        show_mandeh = int(row[0]) if row and row[0] is not None else 0
    except:
        show_mandeh = 0

    cursor.execute("""
        SELECT C_Code
        FROM dbo.CUSTOMER
        WHERE REPLACE(customer_persian, ' ', '') LIKE ?
        AND ISNULL(LTRIM(RTRIM(C_Mobile)), '') <> ''
    """, (f'%{normalized_keyword}%',))
    code_results = cursor.fetchall()
    all_codes = [row[0] for row in code_results]
    cursor.close()
    conn.close()
    
    if not all_codes:
        return jsonify({"status": "error", "message": "هیچ مشتری با این نام یافت نشد."}), 404

    # صفحه‌بندی دستی
    total_results = len(all_codes)
    total_pages = (total_results + per_page - 1) // per_page  # سقف

    if page < 1 or page > total_pages:
        return jsonify({"status": "error", "message": "شماره صفحه خارج از محدوده است."}), 400

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_codes = all_codes[start_idx:end_idx]


    if not code_results:
        return jsonify({"status": "error", "message": "هیچ مشتری با این نام یافت نشد."}), 404

    result_list = []
    for c_code in page_codes:
        full_data = get_full_customer_data(c_code, show_mandeh)
        if full_data:
            result_list.append(full_data)


    return jsonify({
        "status": "ok",
        "keyword": keyword,
        "page": page,
        "per_page": per_page,
        "total_results": total_results,
        "total_pages": total_pages,
        "results": result_list
    })



@holoo_bp.route("/GroupsKala", methods=["GET", "POST"])
@require_api_key
def get_categories_with_subcategories():
    conn = get_article_connection()
    cursor = conn.cursor()

    if cursor is None:
        return jsonify({"error": "Database connection is not available."}), 500

    if request.method == "GET":
        cursor.execute("SELECT M_groupcode, M_groupname, Image FROM M_GROUP")
        main_categories = cursor.fetchall()
        categories_with_subcategories = []

        for main_category in main_categories:
            M_groupcode, M_groupname, M_image = main_category
            sub_categories_list = []

            cursor.execute(
                "SELECT S_groupcode, S_groupname, Image FROM S_GROUP WHERE M_groupcode=?",
                (M_groupcode,),
            )
            sub_categories_query = cursor.fetchall()

            for sub_category in sub_categories_query:
                S_groupcode, S_groupname, S_image = sub_category
                sub_categories_list.append({
                    "S_groupcode": S_groupcode,
                    "S_groupname": S_groupname,
                    "S_image": S_image,
                })

            categories_with_subcategories.append({
                "M_groupcode": M_groupcode,
                "M_groupname": M_groupname,
                "sub_categories": sub_categories_list,
                "M_image": M_image,
            })

        return jsonify(categories_with_subcategories)

    elif request.method == "POST":
        try:
            data = request.get_json()
            m_group = data.get("m_group")
            s_group = data.get("s_group")  # فیلد جدید
            new_image = data.get("image")

            if not m_group or not new_image:
                return jsonify({"error": "فیلدهای m_group و image الزامی هستند."}), 400

            # اگر s_group هم ارسال شده بود:
            if s_group:
                # بررسی وجود هم‌زمان m_group و s_group در S_GROUP
                cursor.execute("""
                    SELECT COUNT(*) FROM S_GROUP 
                    WHERE M_groupcode = ? AND S_groupcode = ?
                """, (m_group, s_group))
                exists = cursor.fetchone()[0]

                if not exists:
                    return jsonify({"error": f"زیرگروه با کد {s_group} برای گروه اصلی {m_group} وجود ندارد."}), 400

                # آپدیت تصویر در جدول S_GROUP
                cursor.execute("""
                    UPDATE S_GROUP SET Image = ? 
                    WHERE M_groupcode = ? AND S_groupcode = ?
                """, (new_image, m_group, s_group))
                conn.commit()

                return jsonify({"message": f"تصویر زیرگروه {s_group} با موفقیت به‌روزرسانی شد."}), 200

            # اگر s_group وجود نداشت فقط M_GROUP رو آپدیت کن
            cursor.execute("SELECT COUNT(*) FROM M_GROUP WHERE M_groupcode = ?", (m_group,))
            exists = cursor.fetchone()[0]

            if not exists:
                return jsonify({"error": f"گروه اصلی با کد {m_group} وجود ندارد."}), 400

            # آپدیت تصویر در جدول M_GROUP
            cursor.execute(
                "UPDATE M_GROUP SET Image = ? WHERE M_groupcode = ?",
                (new_image, m_group)
            )
            conn.commit()

            return jsonify({"message": f"تصویر گروه {m_group} با موفقیت به‌روزرسانی شد."}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

        finally:
            cursor.close()
            conn.close()


@holoo_bp.route('/delete_m_image', methods=['POST'])
@require_api_key
def delete_m_image():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        data = request.get_json()
        m_group = data.get("m_group")

        if not m_group:
            return jsonify({"error": "کد گروه (m_group) ارسال نشده است."}), 400

        # بررسی وجود گروه
        cursor.execute("SELECT Image FROM M_GROUP WHERE M_groupcode = ?", (m_group,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "این دسته‌بندی وجود ندارد."}), 400

        current_image = result[0]

        # آدرس تصویر پیش‌فرض
        default_image_url = "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"

        # بررسی اینکه آیا تصویر از قبل پیش‌فرض بوده
        if current_image == default_image_url:
            return jsonify({"error": "برای این دسته‌بندی تصویری قرار نداده بودید."}), 400

        # بروزرسانی تصویر به پیش‌فرض
        cursor.execute("UPDATE M_GROUP SET Image = ? WHERE M_groupcode = ?", (default_image_url, m_group))
        conn.commit()

        return jsonify({"message": "تصویر دسته‌بندی با موفقیت به مقدار پیش‌فرض تغییر یافت."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()




# Route for rating products
@holoo_bp.route('/admin_rate', methods=['GET', 'POST'])
@require_api_key
def admin_rate():
    # Ensure the 'admin_rate' column exists before anything else
    ensure_admin_rate_column_exists()

    if request.method == 'POST':
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Request must be of type JSON."
            }), 400

        data = request.get_json()
        a_code = data.get('a_code')
        a_name = data.get('a_name', '').strip().replace(' ', '')
        rate = data.get('rate')

        if rate is None:
            return jsonify({
                "status": "error",
                "message": "The 'rate' field is required."
            }), 400

        try:
            rate = int(rate)
            if rate < 1 or rate > 5:
                return jsonify({
                    "status": "error",
                    "message": "The 'rate' value must be between 1 and 5."
                }), 400
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "The 'rate' value must be an integer."
            }), 400

        if not a_code and not a_name:
            return jsonify({
                "status": "error",
                "message": "At least one of 'a_code' or 'a_name' must be provided."
            }), 400

        try:
            conn = get_article_connection()
            cursor = conn.cursor()

            if a_code:
                cursor.execute("SELECT A_Code FROM dbo.ARTICLE WHERE A_Code = ?", (a_code,))
            elif a_name:
                cursor.execute("""
                    SELECT A_Code FROM dbo.ARTICLE
                    WHERE REPLACE(convert_persian, ' ', '') = ?
                """, (a_name,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    "status": "error",
                    "message": "Product not found."
                }), 404

            product_code = row[0]

            cursor.execute("""
                UPDATE dbo.ARTICLE
                SET admin_rate = ?
                WHERE A_Code = ?
            """, (rate, product_code))

            conn.commit()

            return jsonify({
                "status": "success",
                "message": f"Rating {rate} has been successfully registered for product {product_code}.",
                "data": {
                    "a_code": product_code,
                    "admin_rate": rate
                }
            }), 200

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error processing the request: {str(e)}"
            }), 500

        finally:
            cursor.close()
            conn.close()

    # ------------------ GET METHOD ------------------
    if request.method == 'GET':
        try:
            page = int(request.args.get('page', 1))
            per_page = 10
            offset = (page - 1) * per_page

            conn = get_article_connection()
            cursor = conn.cursor()

            # واکشی اطلاعات کامل محصولات به همراه admin_rate
            cursor.execute(f"""
                SELECT A_Code, A_Code_C, A_Name, Sel_Price, VahedCode, Exist, Attribute, 
                    DarsadTakhfif, PriceTakhfif,
                    Sel_Price2, Sel_Price3, Sel_Price4, Sel_Price5, Sel_Price6, Sel_Price7, 
                    Sel_Price8, Sel_Price9, Sel_Price10,
                    EndBuy_Price, A_Max, A_Min, Karton, Image, Seen, Rate_Count, Av_Rate,
                    admin_rate
                FROM dbo.ARTICLE
                WHERE A_Code IS NOT NULL
                AND A_Name IS NOT NULL
                AND Sel_Price IS NOT NULL
                AND Sel_Price > 0
                AND IsActive = 1
                ORDER BY admin_rate DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """, (offset, per_page))

            articles = cursor.fetchall()

            # دریافت لیست واحدها
            cursor.execute("SELECT Unit_Code, Unit_Name FROM UNIT")
            units = {row[0]: row[1] for row in cursor.fetchall()}

            # دریافت لیست کالاهای اشانتیون
            cursor.execute("""
                SELECT Gift_Code FROM dbo.MyGift_WC
                WHERE is_gift = 1 AND Gift_Code IS NOT NULL
            """)
            gifted_codes = {row[0] for row in cursor.fetchall()}

            articles_list = []
            for row in articles:
                is_gifted = row[0] in gifted_codes
                vahed_name = units.get(row[4], "نامشخص")
                try:
                    sel_price = float(row[3]) if row[3] not in [None, ""] else 0
                    darsad_takhfif = float(row[7]) if row[7] not in [None, ""] else 0
                    price_takhfif = float(row[8]) if row[8] not in [None, ""] else 0
                except ValueError:
                    sel_price, darsad_takhfif, price_takhfif = 0, 0, 0

                # محاسبه قیمت نهایی با تخفیف
                if darsad_takhfif > 0:
                    takhfifnahayi = sel_price - ((sel_price * darsad_takhfif) / 100)
                elif price_takhfif > 0:
                    takhfifnahayi = sel_price - price_takhfif
                else:
                    takhfifnahayi = sel_price

                articles_list.append({
                    "FldC_Kala": row[0],
                    "FldACode_C": row[1],
                    "FldN_Kala": row[2],
                    "FldFee": sel_price,
                    "FldMande": int(row[5]) if row[5] not in [None, ""] else 0,
                    "FldN_Vahed": vahed_name,
                    "FldTozihat": row[6] if row[6] else "",
                    "FldFeeBadAzTakhfif": takhfifnahayi,
                    "Sel_Price2": float(row[9]) if row[9] not in [None, ""] else 0,
                    "Sel_Price3": float(row[10]) if row[10] not in [None, ""] else 0,
                    "Sel_Price4": float(row[11]) if row[11] not in [None, ""] else 0,
                    "Sel_Price5": float(row[12]) if row[12] not in [None, ""] else 0,
                    "Sel_Price6": float(row[13]) if row[13] not in [None, ""] else 0,
                    "Sel_Price7": float(row[14]) if row[14] not in [None, ""] else 0,
                    "Sel_Price8": float(row[15]) if row[15] not in [None, ""] else 0,
                    "Sel_Price9": float(row[16]) if row[16] not in [None, ""] else 0,
                    "Sel_Price10": float(row[17]) if row[17] not in [None, ""] else 0,
                    "EndBuyPrice": float(row[18]) if row[18] not in [None, ""] else 0,
                    "FldMax": float(row[19]) if row[19] not in [None, ""] else 0,
                    "FldMin": float(row[20]) if row[20] not in [None, ""] else 0,
                    "FldTedadKarton": int(row[21]) if row[21] not in [None, ""] else 0,
                    "FldImage": row[22] if row[22] else "",
                    "Seen": int(row[23]) if row[23] not in [None, ""] else 0,
                    "RateCount": int(row[24]) if row[24] not in [None, ""] else 0,
                    "AvRate": float(row[25]) if row[25] not in [None, ""] else 0,
                    "admin_rate": float(row[26]) if row[26] not in [None, ""] else 0,
                    "IsGifted": is_gifted
                })

            cursor.execute("SELECT COUNT(*) FROM dbo.ARTICLE WHERE A_Code IS NOT NULL AND A_Name IS NOT NULL AND Sel_Price IS NOT NULL AND Sel_Price > 0 AND IsActive = 1")
            total_records = cursor.fetchone()[0]
            total_pages = (total_records + per_page - 1) // per_page

            return jsonify({
                "status": "success",
                "page": page,
                "total_pages": total_pages,
                "total_records": total_records,
                "articles": articles_list
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

        finally:
            cursor.close()
            conn.close()

            
            
            
            
            
#پاک کردن امتیاز ادمین 
@holoo_bp.route('/reset_admin_rate', methods=['POST'])
@require_api_key
def reset_admin_rate():
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request must be of type JSON."
        }), 400

    data = request.get_json()
    a_code = data.get('a_code')
    a_name = data.get('a_name', '').strip().replace(' ', '')

    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # ✅ اگر کاربر بخواهد همه محصولات را reset کند
        if a_code == 'all' or a_name.lower() == 'all':
            cursor.execute("SELECT COUNT(*) FROM dbo.ARTICLE WHERE admin_rate IS NOT NULL")
            count = cursor.fetchone()[0]

            if count == 0:
                return jsonify({
                    "status": "error",
                    "message": "هیچکدام از محصولات را تا حالا امتیاز دهی نکرده‌اید."
                }), 400

            cursor.execute("UPDATE dbo.ARTICLE SET admin_rate = NULL WHERE admin_rate IS NOT NULL")
            conn.commit()

            return jsonify({
                "status": "success",
                "message": f"امتیاز {count} محصول با موفقیت پاک شد."
            }), 200

        # ✅ اگر کاربر فقط یک محصول خاص را بخواهد reset کند
        if not a_code and not a_name:
            return jsonify({
                "status": "error",
                "message": "At least one of 'a_code' or 'a_name' must be provided."
            }), 400

        # بررسی محصول بر اساس a_code یا a_name
        if a_code:
            a_code = str(a_code).strip()
            cursor.execute("""
                SELECT A_Code, admin_rate FROM dbo.ARTICLE WHERE A_Code = ?
            """, (a_code,))
        else:
            cursor.execute("""
                SELECT A_Code, admin_rate FROM dbo.ARTICLE
                WHERE REPLACE(convert_persian, ' ', '') = ?
            """, (a_name,))

        row = cursor.fetchone()

        if not row:
            return jsonify({
                "status": "error",
                "message": "Product not found."
            }), 404

        product_code, admin_rate = row

        if admin_rate is None:
            return jsonify({
                "status": "error",
                "message": "این محصول توسط شما قبلاً امتیازدهی نشده بود."
            }), 400

        # پاک‌کردن امتیاز
        cursor.execute("UPDATE dbo.ARTICLE SET admin_rate = NULL WHERE A_Code = ?", (product_code,))
        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"The rating for product {product_code} has been reset.",
            "data": {
                "a_code": product_code
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error resetting admin_rate: {str(e)}"
        }), 500

    finally:
        cursor.close()
        conn.close()





# @holoo_bp.route("/ArticleByGroups", methods=["POST"])
# def get_articles_by_groups():
#     conn = None
#     try:
#         data = request.get_json()
#         M_groupcode = data.get("M_groupcode")
#         S_groupcode = data.get("S_groupcode")

#         if not M_groupcode and not S_groupcode:
#             return (
#                 jsonify(
#                     {"error": "حداقل یکی از M_groupcode یا S_groupcode باید ارسال شود"}
#                 ),
#                 400,
#             )

#         conn = get_article_connection()
#         cursor = conn.cursor()
        
#         # بررسی مقدار HideMojoodi
#         cursor.execute("SELECT TOP 1 HideMojoodi FROM TblSetting_forooshgahi")
#         hide_mojoodi_row = cursor.fetchone()
#         hide_mojoodi = bool(hide_mojoodi_row[0]) if hide_mojoodi_row and hide_mojoodi_row[0] is not None else False
        
#         # بررسی مقدار HideNamojood
#         cursor.execute("SELECT TOP 1 HideNamojood FROM TblSetting_forooshgahi")
#         hide_namojood_row = cursor.fetchone()
#         hide_namojood = bool(hide_namojood_row[0]) if hide_namojood_row and hide_namojood_row[0] is not None else False
        
#         # بررسی واحد پولی (ریال یا تومان)
#         cursor.execute("SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
#         vahed_pool_row = cursor.fetchone()
#         is_toman = vahed_pool_row and str(vahed_pool_row[0]).strip().lower() == "toman"




#         where_clause = "WHERE IsActive = 1"
#         params = []

#         # بررسی گروه اصلی
#         if M_groupcode:
#             cursor.execute(
#                 "SELECT 1 FROM M_GROUP WHERE M_groupcode = ?", (M_groupcode,)
#             )
#             if not cursor.fetchone():
#                 return jsonify({"error": "M_groupcode not found"}), 404
#             where_clause += " AND SUBSTRING(A_Code, 1, 2) = ?"
#             params.append(M_groupcode)

#         # بررسی گروه فرعی
#         if S_groupcode:
#             cursor.execute(
#                 "SELECT 1 FROM S_GROUP WHERE S_groupcode = ?", (S_groupcode,)
#             )
#             if not cursor.fetchone():
#                 return jsonify({"error": "S_groupcode not found"}), 404
#             where_clause += " AND SUBSTRING(A_Code, 3, 2) = ?"
#             params.append(S_groupcode)

#         # کوئری برای گرفتن مقالات
#         query = f"""
#             SELECT
#                 A_Code,
#                 A_Code_C,
#                 A_Name,
#                 Sel_Price,
#                 VahedCode,
#                 Exist,
#                 Karton,
#                 Attribute,
#                 DarsadTakhfif,
#                 PriceTakhfif,
#                 EndBuy_Price,
#                 A_Max,
#                 A_Min,
#                 Image
#             FROM Article
#             {where_clause}
#         """

#         cursor.execute(query, params)
#         rows = cursor.fetchall()

#         # گرفتن واحدها
#         cursor.execute("SELECT Unit_Code, Unit_Name FROM UNIT")
#         units = {row[0]: row[1] for row in cursor.fetchall()}

#         # گرفتن کدهای هدیه
#         cursor.execute(
#             "SELECT DISTINCT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL"
#         )
#         gift_codes = {row[0] for row in cursor.fetchall()}
        
#         #عماد
#         # 🔹 اضافه کن: گرفتن کدهای مخفی قیمت
#         cursor.execute("SELECT A_Code FROM HiddenPrice")
#         hidden_price_codes = {row[0] for row in cursor.fetchall()}

#         articles = []
#         for row in rows:
#             (
#                 code,
#                 code_c,
#                 name,
#                 sel_price,
#                 vahed_code,
#                 exist,
#                 karton,
#                 attribute,
#                 d_takhfif,
#                 p_takhfif,
#                 end_buy,
#                 a_max,
#                 a_min,
#                 image,
#             ) = row
            
            
#             image_url = make_image_url(code)

#             # اگر HideNamojood فعال باشد و کالا موجودی نداشته باشد، آن را رد کن
#             if hide_namojood and (exist is None or float(exist) <= 0):
#                 continue


#             try:
#                 sel_price = float(sel_price or 0)
#                 d_takhfif = float(d_takhfif or 0)
#                 p_takhfif = float(p_takhfif or 0)
#             except:
#                 sel_price, d_takhfif, p_takhfif = 0, 0, 0

#             if d_takhfif > 0:
#                 final_price = sel_price - ((sel_price * d_takhfif) / 100)
#             elif p_takhfif > 0:
#                 final_price = sel_price - p_takhfif
#             else:
#                 final_price = sel_price
                    
#             # اگر واحد پول تومان بود، قیمت‌ها رو تقسیم بر 10 کن
#             if is_toman and code not in hidden_price_codes:
#                 sel_price /= 10
#                 final_price /= 10
#                 end_buy = end_buy / 10

                
#             # اگر کد کالا در لیست کدهای مخفی بود قیمت‌ها رو به "برای اطلاع ..." تغییر بده
#             if code in hidden_price_codes:
#                 sel_price_display = "تماس بگیرید"
#                 final_price_display = "تماس بگیرید"
#                 end_buy_display = "تماس بگیرید"
#                 exist_display = "تماس بگیرید"
#             else:
#                 sel_price_display = sel_price
#                 final_price_display = final_price
#                 end_buy_display = float(end_buy or 0)
#                 exist_display = exist or 0
                
#             if hide_mojoodi:
#                 exist_display = "تماس بگیرید"
#             else:
#                 exist_display = exist or 0



#             articles.append(
#                 {
#                     "FldC_Kala": code,
#                     "FldACode_C": code_c,
#                     "FldN_Kala": name,
#                     "FldFee": sel_price_display,
#                     "FldFeeBadAzTakhfif": final_price_display,
#                     "FldN_Vahed": units.get(vahed_code, "نامشخص"),
#                     "FldMande": exist_display,
#                     "FldTedadKarton": karton or 0,
#                     "FldTozihat": attribute or "",
#                     "EndBuyPrice": end_buy_display,
#                     "FldMax": float(a_max or 0),
#                     "FldMin": float(a_min or 0),
#                     "FldImage": image_url,
#                     "IsGifted": code in gift_codes,
#                 }
#             )

#         return jsonify({"total": len(articles), "Articles": articles})

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if conn:
#             conn.close()




@holoo_bp.route("/ArticleByGroups", methods=["POST"])
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

        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی مقدار HideMojoodi
        cursor.execute("SELECT TOP 1 HideMojoodi FROM TblSetting_forooshgahi")
        hide_mojoodi_row = cursor.fetchone()
        hide_mojoodi = bool(hide_mojoodi_row[0]) if hide_mojoodi_row and hide_mojoodi_row[0] is not None else False

        # بررسی مقدار HideNamojood
        cursor.execute("SELECT TOP 1 HideNamojood FROM TblSetting_forooshgahi")
        hide_namojood_row = cursor.fetchone()
        hide_namojood = bool(hide_namojood_row[0]) if hide_namojood_row and hide_namojood_row[0] is not None else False
        
        # بعد از گرفتن gift_codes و hidden_price_codes اینو اضافه کن
        cursor.execute(f"SELECT * FROM dbo.MyGift_WC")
        gift_rows = cursor.fetchall()
        gift_columns = [col[0] for col in cursor.description]

        gifts_by_acode = {}
        for r in gift_rows:
            gift_dict = dict(zip(gift_columns, r))
            gifts_by_acode.setdefault(str(gift_dict["A_Code"]), []).append(gift_dict)


        # بررسی واحد پولی (ریال یا تومان)
        cursor.execute("SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
        vahed_pool_row = cursor.fetchone()
        is_toman = vahed_pool_row and str(vahed_pool_row[0]).strip().lower() == "toman"

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
                Image,
                Rate,
                Seen,
                Av_Rate,
                ISNULL(TedadDarkhasti, 0) AS TedadDarkhasti,
                ISNULL(Rate_Count, 0) AS Rate_Count
            FROM Article
            {where_clause}
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # گرفتن واحدها
        cursor.execute("SELECT Unit_Code, Unit_Name, Unit_Few, Vahed_Vazn FROM UNIT")
        units_raw = cursor.fetchall()
        units = {str(row[0]): row[1] for row in units_raw}
        unit_fews = {str(row[0]): str(row[2]) for row in units_raw if row[2] is not None}
        unit_weights = {str(row[0]): row[3] for row in units_raw if row[3] is not None}

        # گرفتن کدهای هدیه
        cursor.execute(
            "SELECT DISTINCT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL"
        )
        gift_codes = {row[0] for row in cursor.fetchall()}

        # گرفتن کدهای مخفی قیمت
        cursor.execute("SELECT A_Code FROM HiddenPrice")
        hidden_price_codes = {row[0] for row in cursor.fetchall()}

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
                rate,
                seen,
                av_rate,
                tedad_darkhasti,
                rate_count,
            ) = row

            image_url = make_image_url(code)

            vahed_name = units.get(str(vahed_code), "نامشخص")
            unit_few_code = unit_fews.get(str(vahed_code))
            vahed_riz_name = units.get(unit_few_code, "نامشخص") if unit_few_code else "نامشخص"
            vahed_weight = unit_weights.get(str(vahed_code), "نامشخص")

            m_group = code[:2]
            s_group = code[2:4]

            cursor.execute("SELECT M_groupname FROM dbo.M_GROUP WHERE M_groupcode = ?", (m_group,))
            m_groupname_row = cursor.fetchone()
            m_groupname = m_groupname_row[0] if m_groupname_row else ""

            cursor.execute("SELECT S_groupname FROM dbo.S_GROUP WHERE S_groupcode = ? AND M_groupcode = ?", (s_group, m_group))
            s_groupname_row = cursor.fetchone()
            s_groupname = s_groupname_row[0] if s_groupname_row else ""

            # اگر HideNamojood فعال باشد و کالا موجودی نداشته باشد، آن را رد کن
            if hide_namojood and (exist is None or float(exist) <= 0):
                continue

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

            # اگر واحد پول تومان بود، قیمت‌ها رو تقسیم بر 10 کن
            if is_toman and code not in hidden_price_codes:
                sel_price /= 10
                final_price /= 10
                end_buy = end_buy / 10

            # اگر کد کالا در لیست کدهای مخفی بود قیمت‌ها رو به "برای اطلاع ..." تغییر بده
            if code in hidden_price_codes:
                sel_price_display = "تماس بگیرید"
                final_price_display = "تماس بگیرید"
                end_buy_display = "تماس بگیرید"
                exist_display = "تماس بگیرید"
            else:
                sel_price_display = sel_price
                final_price_display = final_price
                end_buy_display = float(end_buy or 0)
                exist_display = exist or 0

            if hide_mojoodi:
                exist_display = "تماس بگیرید"
            else:
                exist_display = exist or 0

            articles.append(
                {
                    "FldC_Kala": code,
                    "FldACode_C": code_c,
                    "FldN_Kala": name,
                    "FldFee": sel_price_display,
                    "FldFeeBadAzTakhfif": final_price_display,
                    "FldN_Vahed": vahed_name,
                    "FldN_Vahed_Riz": vahed_riz_name,
                    "FldVahedVazn": vahed_weight,
                    "FldMande": exist_display,
                    "FldTedadKarton": karton or 0,
                    "FldTozihat": attribute or "",
                    "EndBuyPrice": end_buy_display,
                    "FldMax": float(a_max or 0),
                    "FldMin": float(a_min or 0),
                    "FldImage": image_url,
                    "IsGifted": code in gift_codes,
                    "Rate": rate,
                    "Seen": seen,
                    "Av_Rate": av_rate,
                    "TedadDarkhasti": tedad_darkhasti,
                    "Rate_Count": rate_count,
                    "M_GROUP": m_group,
                    "S_GROUP": s_group,
                    "M_GROUPNAME": m_groupname,
                    "S_GROUPNAME": s_groupname,
                    "FldVahedpool": vahed_pool_row[0] if vahed_pool_row else "rial",
                    "GiftInfo": gifts_by_acode.get(str(code), []),
                }
            )

        return jsonify({"total": len(articles), "Articles": articles})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()




def generate_four_digit_factor_id():
    return f"F-{random.randint(1000, 9999)}"

def get_customer_code_by_mobile(mobile):
    conn = get_article_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT C_Code FROM CUSTOMER WHERE C_Mobile = ?", (mobile,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_current_stock(a_code):
    conn = get_article_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Exist FROM ARTICLE WHERE A_Code = ?", (a_code,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0

def insert_factor(
    order_title, customer_code, factor_id, is_return, visitor_code=None, WEBCOM=1
):
    conn = get_article_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()
        default_date = datetime(1899, 12, 30)
        payment_type_text = "نقدی" if order_title.get("FldPayId") == "1" else "نسیه"
        comment = order_title.get("FldTozihFaktor", "") + f" ({payment_type_text})"
        
        cursor.execute("SELECT ISNULL(MAX(RqIndex2), 0) FROM RQTITLE")
        max_rqindex2 = cursor.fetchone()[0] or 0
        new_rqindex2 = max_rqindex2 + 1
        
        cursor.execute(
            """
            INSERT INTO RQTITLE (
                RqType, R_CusCode, R_Date, T_Time, T_Date,
                SumPrice, Comment, FTakhfif, ShowOrHide, Beianeh,
                OkModir, UserName, RQT_Id, Wait, R_Time, FactorID, PaymentType, RqIndex2, WEBCOM
            ) OUTPUT INSERTED.RqIndex
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 0, 0, ?, 0, 0, ?, ?, ?, ?, ?)
            """,
            (
                "F" if not is_return else "R",
                customer_code,
                now,
                default_date,
                now,
                order_title.get("FldTotalFaktor", 0),
                comment,
                1,
                now,
                factor_id,
                payment_type_text,
                new_rqindex2,
                WEBCOM,
            ),
        )
        rq_index_row = cursor.fetchone()
        if rq_index_row is None or rq_index_row[0] is None:
            raise Exception("Failed to retrieve RqIndex after insert")
        rq_index = rq_index_row[0]
        conn.commit()
        return rq_index
    except Exception as e:
        logging.error(f"Error in insert_factor: {e}")
        raise
    finally:
        conn.close()


def insert_order_details(rq_index, items, is_return=False):
    conn = get_article_connection()
    cursor = conn.cursor()

    inserted_items = []
    blocked_items = []

    try:
        # 1. Fetch currency and 'Allow Sell Over Exist' settings
        # Using the corrected field name: FldP_ForooshBishAzMojoodi
        cursor.execute("SELECT TOP 1 FldVahedpool, FldP_ForooshBishAzMojoodi FROM TblSetting_forooshgahi")
        setting_row = cursor.fetchone()
        
        is_toman_setting = False
        allow_sell_over_exist = False 
        
        if setting_row:
            vahedpool_raw = setting_row[0] if setting_row[0] else "rial"
            is_toman_setting = vahedpool_raw.strip().lower() == "تومان" # Keep this as 'تومان' for Persian
            
            # FldP_ForooshBishAzMojoodi is likely 0 for no, 1 for yes
            allow_sell_over_exist = bool(setting_row[1]) if setting_row[1] is not None else False 

        for item in items:
            try:
                a_code = item.get("FldC_Kala") or item.get("A_Code")
                tedad = int(item.get("FldTedad", 0))
                fee = float(item.get("FldFee", 0)) 
                unit_name = item.get("FldN_Vahed", "عدد")
                
                cursor.execute("SELECT VahedCode FROM ARTICLE WHERE A_Code = ?", (a_code,))
                unit_code_row = cursor.fetchone()
                unit_code = unit_code_row[0] if unit_code_row else None

                # 2. Check stock, conditionally skipping if FldP_ForooshBishAzMojoodi allows
                if not allow_sell_over_exist: 
                    current_stock = get_current_stock(a_code)
                    if tedad > current_stock:
                        blocked_items.append(a_code)
                        logging.warning(
                            f"❌ Insufficient stock for item {a_code}: Requested {tedad}, current {current_stock}"
                        )
                        continue 

                item_comment = item.get("FldTozihat", "")

                # 3. Convert price (fee) based on currency setting
                if is_toman_setting:
                   fee_for_db = fee * 10 
                else:
                   fee_for_db = fee 


                cursor.execute(
                    """
                    INSERT INTO RQDETAIL (
                        RqIndex, RqType, R_ArCode, R_ArCode_C, R_ArName,
                        R_Few, R_FewAval, R_Few2, R_FewAval2, R_Cost, 
                        Unit_Code, R_Commen, Show_Or_Hide, OkReceive,
                        IndexHlp, Selected, RQ_State, R_FewAval3, R_Few3,
                        FewKarton, FewBasteh, Moddat, DarsadTakhfif, TakhfifSatriR
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                    """,
                    (
                        rq_index,
                        "F" if not is_return else "R",
                        a_code,
                        item.get("FldACode_C"),
                        item.get("FldN_Kala"),
                        tedad,
                        fee_for_db, 
                        unit_code,
                        item_comment,
                    ),
                )

                inserted_items.append(a_code)
                logging.info(f"[✅ Logged] Item {a_code} with quantity {tedad}")

            except Exception as item_err:
                logging.error(
                    f"❌ Error inserting item {item.get('FldC_Kala') or item.get('A_Code')}: {item_err}"
                )
                blocked_items.append(item.get("FldC_Kala") or item.get("A_Code"))

        conn.commit()
        logging.info(f"[SUMMARY] Inserted: {inserted_items} | Blocked: {blocked_items}")

        return inserted_items, blocked_items

    finally:
        conn.close()

@holoo_bp.route("/save", methods=["POST"])
@require_api_key
def save_factors_to_holoo():
    try:
        data = request.get_json()

        order_title = data.get("OrderTitle", {})
        items = data.get("OrderDetails", [])

        if not order_title or not items:
            return jsonify({"error": "اطلاعات ناقص است"}), 400

        mobile = order_title.get("FldMobile")
        is_return = order_title.get("IsReturn") == True

        if not mobile:
            return jsonify({"error": "شماره موبایل اجباری است"}), 400

        customer_code = get_customer_code_by_mobile(mobile)
        if not customer_code:
            return (
                jsonify({"error": "کد مشتری یافت نشید یا شماره موبایل نامعتبر است"}),
                400,
            )

        factor_id = generate_four_digit_factor_id()

        rq_index = insert_factor(order_title, customer_code, factor_id, is_return)

        inserted_items, blocked_items = insert_order_details(
            rq_index, items, is_return
        )

        if inserted_items:
            return (
                jsonify(
                    {
                        "status": "سفارش ثبت شد",
                        "RqIndex": rq_index,
                        "FactorID": factor_id,
                        "R_CusCode": customer_code,  
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
                jsonify({"error": "هیچ کالایی ثبت نشد", "details": "اطلاعات نامعتبر"}),
                400,
            )

    except Exception as e:
        logging.error(f"Error in save_factors_to_holoo: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

    
    
    
def fetch_order_details_by_date_range(date_from, date_to, visitor_code=None):
    conn = get_article_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            t.RqIndex, t.RqType, t.R_CusCode, t.R_Date, t.T_Date, t.SumPrice, t.Visitor_Code, FactorID, t.ttvahed,
            d.RqIndex AS DetailRqIndex, d.RqType AS DetailRqType, 
            d.R_ArCode, d.R_ArName, d.R_Few, d.R_Cost, d.dtvahed
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




def get_currency_unit():
    conn = get_article_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT FldVahedpool FROM TblSetting_forooshgahi")
    row = cursor.fetchone()
    return row.FldVahedpool if row else None



@holoo_bp.route("/get_order_details", methods=["POST"])
@require_api_key
def get_order_details():
    data = request.get_json()
    R_Date_From = str(data.get("R_Date_From") or "").strip()
    R_Date_To = str(data.get("R_Date_To") or "").strip()
    visitor_code = str(data.get("Visitor_Code") or "").strip()

    if not R_Date_From or not R_Date_To:
        return jsonify({"error": "R_Date_From and R_Date_To are required"}), 400

    try:
        currency_unit = get_currency_unit()
        rows = fetch_order_details_by_date_range(R_Date_From, R_Date_To, visitor_code)
        orders = {}
        
        conn = get_article_connection()
        cursor = conn.cursor()


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
                        "SumPrice": (
                            row["SumPrice"] * 10 if row.get("ttvahed") == "toman" and currency_unit == "rial"
                            else row["SumPrice"] / 10 if row.get("ttvahed") == "rial" and currency_unit == "toman"
                            else row["SumPrice"]
                        ),
                        "Visitor_Code": row["Visitor_Code"],
                        "FactorID": row["FactorID"],
                    },
                    "RQDETAIL": [],
                }
                cursor.execute(
                    "UPDATE RQTITLE SET ttvahed = ? WHERE RqIndex = ? AND RqType = ? AND ttvahed IS NULL",
                    currency_unit, row["RqIndex"], row["RqType"]
                )



            if row.get("R_ArCode"):
                orders[rq_index]["RQDETAIL"].append(
                    {
                        "RqIndex": row["DetailRqIndex"],
                        "RqType": row["DetailRqType"],
                        "R_ArCode": row["R_ArCode"],
                        "R_ArName": row["R_ArName"],
                        "R_Few": row["R_Few"],
                        "R_Cost": (
                            row["R_Cost"] * 10 if row.get("dtvahed") == "toman" and currency_unit == "rial"
                            else row["R_Cost"] / 10 if row.get("dtvahed") == "rial" and currency_unit == "toman"
                            else row["R_Cost"]
                        ),
                    }
                )
                cursor.execute(
                    "UPDATE RQDETAIL SET dtvahed = ? WHERE RqIndex = ? AND RqType = ? AND R_ArCode = ? AND dtvahed IS NULL",
                    currency_unit, row["DetailRqIndex"], row["DetailRqType"], row["R_ArCode"]
                )
        conn.commit()
        cursor.close()
        conn.close()



        return jsonify({"Orders": list(orders.values())}), 200

    except Exception as e:
        logging.error(f"get_order_details error: {str(e)}")
        return jsonify({"error": str(e)}), 500





def add_dtvahed_column():
    try:
        conn = get_article_connection()  # تابع اتصال به دیتابیس شما
        cursor = conn.cursor()

        # بررسی وجود ستون قبل از اضافه کردن (برای جلوگیری از خطا)
        check_query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'RQDETAIL' AND COLUMN_NAME = 'dtvahed'
        """
        cursor.execute(check_query)
        exists = cursor.fetchone()[0]

        if not exists:
            alter_query = "ALTER TABLE RQDETAIL ADD dtvahed NVARCHAR(50) NULL"
            cursor.execute(alter_query)
            conn.commit()
            print("ستون 'dtvahed' با موفقیت اضافه شد.")
        else:
            print("ستون 'dtvahed' قبلاً وجود دارد.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"خطا در اضافه کردن ستون dtvahed: {e}")




def add_ttvahed_column():
    try:
        conn = get_article_connection()  # تابع اتصال به دیتابیس
        cursor = conn.cursor()

        # بررسی اینکه ستون ttvahed از قبل وجود دارد یا نه
        check_query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'RQTITLE' AND COLUMN_NAME = 'ttvahed'
        """
        cursor.execute(check_query)
        exists = cursor.fetchone()[0]

        if not exists:
            # اضافه کردن ستون جدید
            alter_query = "ALTER TABLE RQTITLE ADD ttvahed NVARCHAR(50) NULL"
            cursor.execute(alter_query)
            conn.commit()
            print("ستون 'ttvahed' با موفقیت به جدول RQTITLE اضافه شد.")
        else:
            print("ستون 'ttvahed' قبلاً وجود دارد.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"خطا در اضافه کردن ستون ttvahed: {e}")






# @holoo_bp.route("/get_order_details", methods=["POST"])
# def get_order_details():
#     data = request.get_json()
#     R_Date_From = str(data.get("R_Date_From") or "").strip()
#     R_Date_To = str(data.get("R_Date_To") or "").strip()
#     visitor_code = str(data.get("Visitor_Code") or "").strip()

#     if not R_Date_From or not R_Date_To:
#         return jsonify({"error": "R_Date_From and R_Date_To are required"}), 400

#     try:
#         rows = fetch_order_details_by_date_range(R_Date_From, R_Date_To, visitor_code)
#         orders = {}

#         for row in rows:
#             rq_index = row["RqIndex"]

#             if rq_index not in orders:
#                 orders[rq_index] = {
#                     "RQTITLE": {
#                         "RqIndex": row["RqIndex"],
#                         "RqType": row["RqType"],
#                         "R_CusCode": row["R_CusCode"],
#                         "R_Date": row["R_Date"],
#                         "T_Date": row["T_Date"],
#                         "SumPrice": row["SumPrice"],
#                         "Visitor_Code": row["Visitor_Code"],
#                         "FactorID": row["FactorID"],
#                     },
#                     "RQDETAIL": [],
#                 }

#             if row.get("R_ArCode"):
#                 orders[rq_index]["RQDETAIL"].append(
#                     {
#                         "RqIndex": row["DetailRqIndex"],
#                         "RqType": row["DetailRqType"],
#                         "R_ArCode": row["R_ArCode"],
#                         "R_ArName": row["R_ArName"],
#                         "R_Few": row["R_Few"],
#                         "R_Cost": row["R_Cost"],
#                     }
#                 )

#         return jsonify({"Orders": list(orders.values())}), 200

#     except Exception as e:
#         logging.error(f"get_order_details error: {str(e)}")
#         return jsonify({"error": str(e)}), 500


            
            
            
            
            
            
class ReportService:
    def __init__(self):
        self.conn = get_article_connection()

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
                    "SELECT Moien_Code_Bed, Tafzili_Code_Bed FROM CUSTOMER WHERE C_Code=?", (
                        code,)
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
                        "SELECT Fac_Code, C_Code, Fac_Date, Fac_Type FROM FACTURE WHERE Sanad_Code = ?", (
                            sanad_code,)
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
                            "SELECT C_Mobile, C_Name FROM CUSTOMER WHERE C_Code = ?", (
                                fact_c_code,)
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
                            order_details.append({
                                "Kala_Name": art[3] or "",
                                "Few_Article": art[4] or 0,
                                "Price_BS": art[5] or 0,
                                "VahedCode": art[6] or "",
                            })

                    mande_satri = bed - bes
                    sum_mande += mande_satri

                    result_list.append({
                        "Sanad_Code": sanad_code,
                        "DateTime": fact_date.strftime("%Y-%m-%d %H:%M:%S") if fact_date else None,
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
                        "Sanad_Date": sanad_date.strftime("%Y-%m-%d") if sanad_date else None,
                    })

            return result_list

        except Exception as e:
            logging.error(f"Error in get_report: {e}")
            logging.error(traceback.format_exc())
            return []


def send_moien_by_mobile(mobile, take, start_date=None, end_date=None):
    try:
        conn = get_article_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT C_Code FROM CUSTOMER WHERE C_Mobile=?", (mobile,))
        user = cursor.fetchone()
        if not user:
            return None

        c_code = user[0]
        report_service = ReportService()
        result = report_service.get_report(c_code, take, start_date=start_date, end_date=end_date)
        report_service.close()
        cursor.close()
        conn.close()
        return result

    except Exception as e:
        logging.error(f"Error in send_moien_by_mobile: {e}")
        logging.error(traceback.format_exc())
        return None



@holoo_bp.route("/send_all_moien", methods=["POST"])
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



@holoo_bp.route("/send_moien_single_mobile", methods=["POST"])
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
            return jsonify({"message": "فرمت تاریخ‌ها باید به صورت yyyy-mm-dd باشد"}), 400

        result = send_moien_by_mobile(
            mobile, take, start_date=start_date_obj, end_date=end_date_obj)

        if result:
            return jsonify({
                "message": "گزارش معین برای شماره موبایل دریافت شد",
                "data": result,
            }), 200
        else:
            return jsonify({"message": "هیچ گزارشی برای این شماره پیدا نشد"}), 404

    except Exception as e:
        logging.error(f"Error in send_moien_single_mobile: {e}")
        logging.error(traceback.format_exc())
        return jsonify({
            "message": "خطا در دریافت گزارش برای شماره موبایل",
            "error": str(e),
        }), 500

        
@holoo_bp.route('/increase_percent_price', methods=['POST'])
@require_api_key
def increase_percent():
    data = request.get_json()
    a_code = data.get("a_code")
    percent = data.get("percent")

    if not a_code or percent is None:
        return jsonify({"error": "Both 'a_code' and 'percent' are required."}), 400

    try:
        # اتصال به دیتابیس کاربر (بر اساس ApiKey یا اتصال ثابت)
        conn = get_article_connection()  # تابعی که کانکشن رو می‌سازه، از قبل باید داشته باشی
        cursor = conn.cursor()

        cursor.execute("SELECT Sel_Price FROM dbo.ARTICLE WHERE A_Code = ?", (a_code,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Product not found"}), 404

        old_price = row[0] or 0
        try:
            percent = float(percent)
        except ValueError:
            return jsonify({"error": "Percent must be a number"}), 400

        new_price = old_price + (old_price * percent / 100)

        return jsonify({
            "a_code": a_code,
            "old_price": old_price,
            "percent_added": percent,
            "new_price": round(new_price, 2)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    

@holoo_bp.route('/update_setting', methods=['POST', 'GET'])
@require_api_key
def update_setting():
    
    if request.method == 'GET':
        conn = get_article_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT WMandeHesab, FldP_ForooshBishAzMojoodi, FldMarjooii, FldTaiidAdmin,
        FldNameForooshgah, FldTellForooshgah, FldAddressForooshgah, FldKharidBiashAz,
        FldZamanTahvil, WSetTip, WSetEshan, WShowMoiens, AddFactorComment, ShowReport,
        Shomare_Card, HideExist, ExpireLogin, HideMojoodi, HideNamojood, FldVahedpool, Logo
        FROM TblSetting_forooshgahi
            """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            base_url = request.host_url.rstrip("/")
            logo_url = row.Logo if row.Logo else ""

            # اگر لوگو موجود بود، لینک‌های ریسایز شده بساز
            if logo_url:
                filename = os.path.basename(logo_url)
                logo_192 = f"{base_url}/static/logos/192_{filename}"
                logo_512 = f"{base_url}/static/logos/512_{filename}"
            else:
                logo_192 = ""
                logo_512 = ""

        if row:
            return jsonify({
                "mandeh": row.WMandeHesab,
                "forooshbishazhad": row.FldP_ForooshBishAzMojoodi,
                "marjooii": row.FldMarjooii,
                "taiid": row.FldTaiidAdmin,
                "nameforooshgah": row.FldNameForooshgah,
                "FldTellForooshgah": row.FldTellForooshgah,
                "FldAddressForooshgah": row.FldAddressForooshgah,
                "FldKharidBiashAz": row.FldKharidBiashAz,
                "FldZamanTahvil": row.FldZamanTahvil,
                "WSetTip": row.WSetTip,
                "WSetEshan": row.WSetEshan,
                "WShowMoiens": row.WShowMoiens,
                "AddFactorComment": row.AddFactorComment,
                "ShowReport": row.ShowReport,
                "Shomare_Card": row.Shomare_Card,
                "HideExist": row.HideExist,
                "ExpireLogin": row.ExpireLogin,
                "hidemojoodi": row.HideMojoodi,
                "hidenamojood": row.HideNamojood,
                "FldVahedPool":row.FldVahedpool,
                "logo": logo_url,
                "logo_192": logo_192,
                "logo_512": logo_512
            })

        else:
            return jsonify({"status": "error", "message": "تنظیماتی یافت نشد."}), 404

    
    data = request.get_json()
    


    if not data:
        return jsonify({"status": "error", "message": "درخواست نامعتبر است."}), 400

    mandeh_raw = data.get('mandeh', None)
    foroosh_raw = data.get('forooshbishazhad', None)
    marjooii_raw = data.get('marjooii', None)
    taiid_raw = data.get('taiid', None)
    name_forooshgah_raw = data.get('nameforooshgah', '').strip()
    tell_forooshgah_raw = data.get('tellforooshgah', '').strip()
    address_forooshgah_raw = data.get('addressforooshgah','').strip()
    vahedpool_raw = data.get('FldVahedPool', '').strip().lower()
    gift_raw = data.get('gift', None)
    hide_exist_raw = data.get('hide_exist', None)
    expire_login_raw = data.get('expire_login', None)
    hidemojoodi_raw = data.get('hidemojoodi', None)
    hidenamojood_raw = data.get('hidenamojood', None)

    updates = {}
    errors = []

    # بررسی mandeh
    if mandeh_raw is not None and mandeh_raw != '':
        try:
            mandeh_value = int(mandeh_raw)
            if mandeh_value in [0, 1]:
                updates['WMandeHesab'] = mandeh_value
            else:
                errors.append("مقدار mandeh فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار mandeh فقط می‌تواند 0 یا 1 باشد.")

    # بررسی forooshbishazhad
    if foroosh_raw is not None and foroosh_raw != '':
        try:
            foroosh_value = int(foroosh_raw)
            if foroosh_value in [0, 1]:
                updates['FldP_ForooshBishAzMojoodi'] = foroosh_value
            else:
                errors.append("مقدار forooshbishazhad فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار forooshbishazhad فقط می‌تواند 0 یا 1 باشد.")
            
    # بررسی marjooii
    if marjooii_raw is not None and marjooii_raw != '':
        try:
            marjooii_value = int(marjooii_raw)
            if marjooii_value in [0, 1]:
                updates['FldMarjooii'] = marjooii_value
            else:
                errors.append("مقدار marjooii فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار marjooii فقط می‌تواند 0 یا 1 باشد.")
            
    # بررسی taiid
    if taiid_raw is not None and taiid_raw != '':
        try:
            taiid_value = int(taiid_raw)
            if taiid_value in [0, 1]:
                updates['FldTaiidAdmin'] = taiid_value
            else:
                errors.append("مقدار taiid فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار taiid فقط می‌تواند 0 یا 1 باشد.")
            
    # بررسی nameforooshgah
    if name_forooshgah_raw:
        if len(name_forooshgah_raw) > 100:
            errors.append("نام فروشگاه باید کمتر از 100 کاراکتر باشد.")
        else:
            updates['FldNameForooshgah'] = name_forooshgah_raw
            
    # بررسی tellforooshgah
    if tell_forooshgah_raw:
        if len(tell_forooshgah_raw) > 50:
            errors.append("شماره تلفن را به صورت صحیح وارد کنید.")
        else:
            updates['FldTellForooshgah'] = tell_forooshgah_raw
            
    # بررسی addressforooshgah
    if address_forooshgah_raw:
        if len(address_forooshgah_raw) > 200:
            errors.append("لطفا آدرس فروشگاه را با کمتر از 200 کاراکتر وارد کنید")
        else:
            updates['FldAddressForooshgah'] = address_forooshgah_raw
            
    # بررسی vahedpool
    if vahedpool_raw:
        if vahedpool_raw not in ['toman', 'rial']:
            errors.append("مقدار vahedpool فقط می‌تواند 'toman' یا 'rial' باشد.")
        else:
            updates['FldVahedPool'] = vahedpool_raw
            
    # بررسی gift
    if gift_raw is not None and gift_raw != '':
        try:
            gift_value = int(gift_raw)
            if gift_value in [0, 1]:
                updates['WSetEshan'] = gift_value
            else:
                errors.append("مقدار gift فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار gift فقط می‌تواند 0 یا 1 باشد.")
            
            
    # بررسی shomare_card
    shomare_card_raw = data.get('shomare_card', '').strip()
    if shomare_card_raw:
        if not shomare_card_raw.isdigit():
            errors.append("شماره کارت فقط باید شامل ارقام باشد.")
        elif len(shomare_card_raw) != 16:
            errors.append("شماره کارت باید دقیقاً 16 رقم باشد.")
        else:
            updates['Shomare_Card'] = shomare_card_raw
            
    # بررسی hide_exist
    if hide_exist_raw is not None and hide_exist_raw != '':
        try:
            hide_exist_value = int(hide_exist_raw)
            if hide_exist_value in [0, 1]:
                updates['HideExist'] = hide_exist_value
            else:
                errors.append("مقدار hide_exist فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار hide_exist فقط می‌تواند 0 یا 1 باشد.")
            
    # بررسی expire_login
    if expire_login_raw is not None and expire_login_raw != '':
        try:
            expire_login_value = int(expire_login_raw)
            if expire_login_value in [0, 1]:
                updates['ExpireLogin'] = expire_login_value
            else:
                errors.append("مقدار expire_login فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار expire_login فقط می‌تواند 0 یا 1 باشد.")
            
    # بررسی hidemojoodi
    if hidemojoodi_raw is not None and hidemojoodi_raw != '':
        try:
            hidemojoodi_value = int(hidemojoodi_raw)
            if hidemojoodi_value in [0, 1]:
                updates['HideMojoodi'] = hidemojoodi_value
            else:
                errors.append("مقدار hidemojoodi فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار hidemojoodi فقط می‌تواند 0 یا 1 باشد.")

    # بررسی hidenamojood
    if hidenamojood_raw is not None and hidenamojood_raw != '':
        try:
            hidenamojood_value = int(hidenamojood_raw)
            if hidenamojood_value in [0, 1]:
                updates['HideNamojood'] = hidenamojood_value
            else:
                errors.append("مقدار hidenamojood فقط می‌تواند 0 یا 1 باشد.")
        except (ValueError, TypeError):
            errors.append("مقدار hidenamojood فقط می‌تواند 0 یا 1 باشد.")

    if errors:
        return jsonify({"status": "error", "message": " / ".join(errors)}), 400

    if updates:
        try:
            conn = get_article_connection()
            cursor = conn.cursor()

            for column, value in updates.items():
                cursor.execute(f"UPDATE TblSetting_forooshgahi SET {column} = ?", (value,))

            conn.commit()
            cursor.close()
            conn.close()

            changed_fields = ', '.join([f"{k} = {v}" for k, v in updates.items()])
            return jsonify({
                "status": "ok",
                "message": f"تنظیمات با موفقیت به‌روزرسانی شد: {changed_fields}"
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"خطا در ذخیره‌سازی: {str(e)}"}), 500

    # هیچ مقداری برای به‌روزرسانی ارسال نشده
    return jsonify({
        "status": "ok",
        "message": "هیچ مقداری برای تغییر ارسال نشد. تنظیمات بدون تغییر باقی ماند."
    })
    
    
    
@holoo_bp.route("/Search_Holoo_Articles", methods=["GET"])
@require_api_key
def search_holoo_articles():
    import math
    from flask import request, jsonify

    def normalize_search_input(text):
        replacements = {
            "ی": "ي",
            "ئ": "ي",
            "ک": "ك",
            "ۀ": "ه",
            "ة": "ه",
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
            "‌": "",
            "ـ": "",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "٫": ".",
            "٬": ",",
            "(": "(",
            ")": ")",
        }
        for f, r in replacements.items():
            text = text.replace(f, r)
        return text.strip()

    try:
        conn = get_article_connection()
        cursor = conn.cursor()
        
        # بررسی مقدار FldVahedpool
        cursor.execute("SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
        vahedpool_row = cursor.fetchone()
        vahedpool = vahedpool_row[0] if vahedpool_row and vahedpool_row[0] else "rial"
        vahedpool = "toman" if vahedpool.strip().lower() == "toman" else "rial"
        
        # بررسی مقدار HideMojoodi
        cursor.execute("SELECT TOP 1 HideMojoodi FROM TblSetting_forooshgahi")
        hide_mojoodi_row = cursor.fetchone()
        hide_mojoodi = bool(hide_mojoodi_row[0]) if hide_mojoodi_row and hide_mojoodi_row[0] is not None else False
        
        # بررسی تنظیمات
        cursor.execute("SELECT TOP 1 FldVahedpool, HideMojoodi, HideNamojood FROM TblSetting_forooshgahi")
        setting_row = cursor.fetchone()
        vahedpool = setting_row[0].strip().lower() if setting_row and setting_row[0] else "rial"
        vahedpool = "toman" if vahedpool == "toman" else "rial"
        hide_mojoodi = bool(setting_row[1]) if setting_row and setting_row[1] is not None else False
        hide_namojood = bool(setting_row[2]) if setting_row and setting_row[2] is not None else False


        search_term = request.args.get("search", "").strip()
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        offset = (page - 1) * per_page

        if not search_term:
            return jsonify({"error": "پارامتر جستجو ارسال نشده است"}), 400

        search_term = normalize_search_input(search_term)
        search_filter = f"%{search_term}%"
        
        where_clause = """
            (
                REPLACE(REPLACE(REPLACE(A_Name, N'ی', N'ي'), N'ک', N'ك'), N'ئ', N'ي') LIKE ? 
                OR A_Code LIKE ?
            )
            AND A_Code IS NOT NULL AND A_Name IS NOT NULL 
            AND Sel_Price IS NOT NULL AND Sel_Price > 0 
            AND IsActive = 1
        """
        if hide_namojood:
            where_clause += " AND Exist > 0"


        # تعداد کل رکوردها
        count_query = f"SELECT COUNT(*) FROM article WHERE {where_clause}"
        cursor.execute(count_query, (search_filter, search_filter))
        total_items = cursor.fetchone()[0]
        total_pages = math.ceil(total_items / per_page)

        # اطلاعات مقالات
        data_query = f"""
            SELECT * FROM (
                SELECT 
                    A_Code, A_Code_C, A_Name, Sel_Price, VahedCode, Exist, Attribute,
                    DarsadTakhfif, PriceTakhfif, Sel_Price2, Sel_Price3, Sel_Price4,
                    Sel_Price5, Sel_Price6, Sel_Price7, Sel_Price8, Sel_Price9, Sel_Price10,
                    EndBuy_Price, A_Max, A_Min, Karton, Image,
                    ROW_NUMBER() OVER (ORDER BY A_Name ASC) AS RowNum
                FROM article
                WHERE {where_clause}
            ) AS Result
            WHERE RowNum BETWEEN ? AND ?
        """

        start_row = offset + 1
        end_row = offset + per_page
        cursor.execute(data_query, (search_filter, search_filter, start_row, end_row))

        articles = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

        # هدیه‌ها
        cursor.execute(
            "SELECT DISTINCT Gift_Code FROM dbo.MyGift_WC WHERE is_gift = 1 AND Gift_Code IS NOT NULL"
        )
        gifted_codes = set(row[0] for row in cursor.fetchall())
        
        # گرفتن تمام اطلاعات هدایا
        cursor.execute("SELECT * FROM dbo.MyGift_WC")
        gift_rows = cursor.fetchall()
        gift_columns = [col[0] for col in cursor.description]

        gifts_by_acode = {}
        for r in gift_rows:
            gift_dict = dict(zip(gift_columns, r))
            gifts_by_acode.setdefault(str(gift_dict["A_Code"]), []).append(gift_dict)


        # واحدها
        cursor.execute("SELECT Unit_Code, Unit_Name FROM UNIT")
        units = {row[0]: row[1] for row in cursor.fetchall()}

        articles_list = []
        # دریافت کدهای کالاهایی که باید قیمت‌شان مخفی باشد
        cursor.execute("SELECT A_Code FROM HiddenPrice")
        hidden_price_codes = set(row[0] for row in cursor.fetchall())


        for row in articles:
            row_dict = dict(zip(columns, row))
            sel_price = float(row[3]) if row[3] else 0
            darsad_takhfif = float(row[7]) if row[7] else 0
            price_takhfif = float(row[8]) if row[8] else 0
            article_code = row_dict["A_Code"]

            if darsad_takhfif > 0:
                final_price = sel_price - ((sel_price * darsad_takhfif) / 100)
            elif price_takhfif > 0:
                final_price = sel_price - price_takhfif
            else:
                final_price = sel_price
                
            # بررسی اینکه آیا باید قیمت مخفی شود
            if row[0] in hidden_price_codes:
                sel_price = "تماس بگیرید"
                final_price = "تماس بگیرید"
                end_buy_price = "تماس بگیرید"
                mande = "تماس بگیرید"
            else:
                if darsad_takhfif > 0:
                    final_price = sel_price - ((sel_price * darsad_takhfif) / 100)
                elif price_takhfif > 0:
                    final_price = sel_price - price_takhfif
                else:
                    final_price = sel_price
                mande = "تماس بگیرید" if hide_mojoodi else (int(row[5]) if row[5] else 0)
                end_buy_price = float(row[18]) if row[18] else 0
            # اگر toman بود، قیمت‌ها رو تقسیم بر 10 کن
            if vahedpool == "toman":
                sel_price /= 10
                final_price /= 10
                row = list(row)
                for i in range(9, 18):
                    if row[i]:
                        row[i] = float(row[i]) / 10
                        
            
            image_url = make_image_url(article_code)

            # === ✅ اضافه کردن استخراج گروه کالاها ===
            a_code = row[0]  # A_Code
            m_group = a_code[:2]
            s_group = a_code[2:4]

            cursor.execute("SELECT M_groupname FROM dbo.M_GROUP WHERE M_groupcode = ?", (m_group,))
            m_groupname_row = cursor.fetchone()
            m_groupname = m_groupname_row[0] if m_groupname_row else ""
            
            cursor.execute("""
                SELECT S_groupname FROM dbo.S_GROUP 
                WHERE S_groupcode = ? AND M_groupcode = ?
            """, (s_group, m_group))
            s_groupname_row = cursor.fetchone()
            s_groupname = s_groupname_row[0] if s_groupname_row else ""

            articles_list.append(
                {
                    "FldC_Kala": row[0],
                    "FldACode_C": row[1],
                    "FldN_Kala": row[2],
                    "FldFee": sel_price,
                    "FldMande": mande,
                    "FldN_Vahed": units.get(row[4], "نامشخص"),
                    "FldTozihat": row[6] or "",
                    "FldFeeBadAzTakhfif": final_price,
                    "Sel_Price2": float(row[9]) if row[9] else 0,
                    "Sel_Price3": float(row[10]) if row[10] else 0,
                    "Sel_Price4": float(row[11]) if row[11] else 0,
                    "Sel_Price5": float(row[12]) if row[12] else 0,
                    "Sel_Price6": float(row[13]) if row[13] else 0,
                    "Sel_Price7": float(row[14]) if row[14] else 0,
                    "Sel_Price8": float(row[15]) if row[15] else 0,
                    "Sel_Price9": float(row[16]) if row[16] else 0,
                    "Sel_Price10": float(row[17]) if row[17] else 0,
                    "EndBuyPrice": end_buy_price,
                    "FldMax": float(row[19]) if row[19] else 0,
                    "FldMin": float(row[20]) if row[20] else 0,
                    "FldTedadKarton": int(row[21]) if row[21] else 0,
                    "FldImage": image_url,
                    "IsGifted": row[0] in gifted_codes,
                    "M_GROUP": m_group,
                    "FldImage": image_url,
                    "S_GROUP": s_group,
                    "M_GROUPNAME": m_groupname,
                    "S_GROUPNAME": s_groupname,
                    "GiftInfo": gifts_by_acode.get(str(row[0]), []),
                }
            )

        return jsonify(
            {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "shown_this_page": len(articles_list),
                "total_pages": total_pages,
                "FldVahedpool": vahedpool,
                "Articles": articles_list,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()



@holoo_bp.route('/admin_settip', methods=['POST'])
@require_api_key
def admin_settip():
    allowed_settips = [
        'Sel_Price', 'Sel_Price2', 'Sel_Price3', 'Sel_Price4', 'Sel_Price5',
        'Sel_Price6', 'Sel_Price7', 'Sel_Price8', 'Sel_Price9', 'Sel_Price10'
    ]

    data = request.get_json()

    if not data or 'c_code' not in data or 'settip' not in data:
        return jsonify({"error": "شما باید هر دو فیلد را وارد کنید"}), 400

    c_code = data['c_code']
    settip = data['settip']

    if settip not in allowed_settips:
        return jsonify({"error": "تیپ قیمتی که وارد کرده‌اید وجود ندارد"}), 400

    conn = get_article_connection()
    cursor = conn.cursor()

    try:
        # بررسی وجود c_code در جدول CUSTOMER
        cursor.execute("SELECT 1 FROM dbo.CUSTOMER WHERE C_Code = ?", (c_code,))
        if cursor.fetchone() is None:
            return jsonify({"error": "مشتری با این کد وجود ندارد"}), 400

        # بررسی وجود c_code در جدول admin_settip
        cursor.execute("SELECT 1 FROM dbo.admin_settip WHERE C_Code = ?", (c_code,))
        if cursor.fetchone():
            # اگر قبلاً وجود دارد، بروزرسانی کن
            cursor.execute("""
                UPDATE dbo.admin_settip
                SET settip = ?
                WHERE C_Code = ?
            """, (settip, c_code))
        else:
            # در غیر این صورت، درج جدید انجام بده
            cursor.execute("""
                INSERT INTO dbo.admin_settip (C_Code, settip)
                VALUES (?, ?)
            """, (c_code, settip))

        conn.commit()
        return jsonify({"message": "اطلاعات با موفقیت ذخیره شد"}), 200

    except Exception as e:
        return jsonify({"error": f"خطا در ثبت اطلاعات: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()



@holoo_bp.route('/products_information', methods=['POST'])
@require_api_key
def product_information():
    data = request.get_json()

    if not data or 'a_code' not in data:
        return jsonify({'error': 'a_code is required'}), 400

    a_code = data['a_code']
    conn = get_article_connection()
    cursor = conn.cursor()

    # بررسی اینکه آیا قیمت محصول مخفی است یا نه
    cursor.execute("SELECT 1 FROM HiddenPrice WHERE A_Code = ?", (a_code,))
    hide_price_result = cursor.fetchone()
    price_hidden = hide_price_result is not None
    
    # بررسی مقدار HideMojoodi
    cursor.execute("SELECT TOP 1 HideMojoodi FROM TblSetting_forooshgahi")
    hide_mojoodi_row = cursor.fetchone()
    hide_mojoodi = bool(hide_mojoodi_row[0]) if hide_mojoodi_row and hide_mojoodi_row[0] is not None else False
    
    # بررسی مقدار HideNamojood
    cursor.execute("SELECT TOP 1 HideNamojood FROM TblSetting_forooshgahi")
    hide_namojood_row = cursor.fetchone()
    hide_namojood = bool(hide_namojood_row[0]) if hide_namojood_row and hide_namojood_row[0] is not None else False

    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # اجرای SELECT
        select_query = """
            SELECT A_Code, A_Code_c, A_Name, Buy_Price, EndBuy_Price, Sel_Price, Exist, Exist2,
                   A_Min, A_Max, First_exist, Exist_Mandeh, FewTakhfif, DarsadTakhfif,
                   VahedCode, IsActive, Rate, Seen, Av_Rate, 
                   ISNULL(TedadDarkhasti, 0) AS TedadDarkhasti,
                   ISNULL(Rate_Count, 0) AS Rate_Count,
                   Tozihat,
                   Karton,
                   Sel_Price10
            FROM ARTICLE
            WHERE A_Code = ?
        """
        
        image_url = make_image_url(a_code)

        cursor.execute(select_query, (a_code,))
        row = cursor.fetchone()

        if row:
            # اگر HideNamojood فعال باشد و کالا موجودی نداشته باشد، نمایش نده
            if hide_namojood and row[6] is not None and float(row[6]) <= 0:
                return jsonify({
                    "status": "error",
                    "message": "این کالا موجود نیست."
                }), 404

            # استخراج ستون‌ها همینجا و قبل از اجرای کوئری جدید
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))
            result["Image"] = image_url  # جایگزینی عکس با خروجی تابع make_image_url

            # اگر قیمت باید مخفی شود
            if price_hidden:
                hide_msg = "تماس بگیرید"
                for key in ["Buy_Price", "EndBuy_Price", "Sel_Price", "Sel_Price10"]:
                    result[key] = hide_msg
                result["Exist"] = "تماس بگیرید"
                
            # اگر HideMojoodi فعال باشد، موجودی‌ها را با "تماس بگیرید" جایگزین کن
            if hide_mojoodi:
                for key in ["Exist", "Exist2", "Exist_Mandeh"]:
                    result[key] = "تماس بگیرید"

            # استخراج گروه‌ها از کد کالا
            m_group = a_code[:2]
            s_group = a_code[2:4]

            cursor.execute("SELECT M_groupname FROM dbo.M_GROUP WHERE M_groupcode = ?", (m_group,))
            m_groupname_row = cursor.fetchone()
            m_groupname = m_groupname_row[0] if m_groupname_row else ""

            cursor.execute(""" 
                SELECT S_groupname FROM dbo.S_GROUP 
                WHERE S_groupcode = ? AND M_groupcode = ? 
            """, (s_group, m_group))
            s_groupname_row = cursor.fetchone()
            s_groupname = s_groupname_row[0] if s_groupname_row else ""

            result['M_GROUP'] = m_group
            result['S_GROUP'] = s_group
            result['M_GROUPNAME'] = m_groupname
            result['S_GROUPNAME'] = s_groupname


            # حالا واحد پولی رو بررسی کن
            cursor.execute(
                "SELECT TOP 1 FldVahedpool FROM TblSetting_forooshgahi")
            pool_row = cursor.fetchone()
            currency = pool_row[0].lower(
            ) if pool_row and pool_row[0] else "rial"

            # اگر واحد پولی تومان بود، قیمت‌ها رو تقسیم بر 10 کن
            if currency == "toman" and not price_hidden:
                for key in ["Sel_Price", "Buy_Price", "EndBuy_Price"]:
                    if key in result and isinstance(result[key], (int, float)):
                        result[key] = result[key] / 10
            # افزودن مقدار ستون FldVahedpool به پاسخ
            result["FldVahedpool"] = pool_row[0] if pool_row and pool_row[0] else "rial"

            # 🟡 افزودن اطلاعات واحدها
            cursor.execute(
                "SELECT Unit_Code, Unit_Name, Unit_Few, Vahed_Vazn FROM UNIT")
            units_raw = cursor.fetchall()
            units = {str(row[0]): row[1] for row in units_raw}
            unit_fews = {str(row[0]): str(row[2])
                         for row in units_raw if row[2] is not None}
            unit_weights = {str(row[0]): row[3]
                            for row in units_raw if row[3] is not None}

            result["units"] = units
            result["unit_fews"] = unit_fews
            result["unit_weights"] = unit_weights

            # 🔸 دریافت اطلاعات واحد کالا
            vahed_code = result.get("VahedCode")
            vahed_code_str = str(vahed_code)
            vahed_name = units.get(vahed_code_str, "نامشخص")
            unit_few_code = unit_fews.get(vahed_code_str)
            vahed_riz_name = units.get(
                unit_few_code, "نامشخص") if unit_few_code else "نامشخص"
            vahed_weight = unit_weights.get(vahed_code_str, "نامشخص")

            # 🔸 افزودن مقادیر به پاسخ
            result["FldN_Vahed"] = vahed_name
            result["FldN_Vahed_Riz"] = vahed_riz_name
            result["FldVahedVazn"] = vahed_weight

            # افزایش مقدار seen
            update_query = "UPDATE ARTICLE SET Seen = ISNULL(Seen, 0) + 1 WHERE A_Code = ?"
            cursor.execute(update_query, (a_code,))
            conn.commit()

            return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    # اگر به هر دلیلی به اینجا رسیدیم یعنی درخواست یا داده مشکل داشته
    return jsonify({
        "status": "error",
        "message": "درخواست نامعتبر است یا داده ارسالی ناقص است."
        }), 400
            
            
            
@holoo_bp.route('/shegeftangiz', methods=['GET'])
@require_api_key
def shegeftangiz():
    import math
    from flask import jsonify

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        offset = (page - 1) * per_page
        start_row = offset + 1
        end_row = offset + per_page

        conn = get_article_connection()
        cursor = conn.cursor()

        # گرفتن نوع واحد پول از تنظیمات
        # گرفتن نوع واحد پول و مقدار HideMojoodi از تنظیمات
        cursor.execute("SELECT TOP 1 FldVahedpool, HideMojoodi FROM TblSetting_forooshgahi")
        setting_row = cursor.fetchone()
        fld_vahedpool_raw = setting_row[0] if setting_row and setting_row[0] else "rial"
        hide_mojoodi = bool(setting_row[1]) if setting_row and setting_row[1] is not None else False
        vahedpool = "toman" if fld_vahedpool_raw.strip().lower() == "toman" else "rial"


        # گرفتن تعداد کل محصولات دارای تخفیف
        count_query = """
            SELECT COUNT(*) 
            FROM article
            WHERE Sel_Price10 < Sel_Price AND Sel_Price > 0 AND Sel_Price10 > 0 AND IsActive = 1
        """
        cursor.execute(count_query)
        total_items = cursor.fetchone()[0]
        total_pages = math.ceil(total_items / per_page)

        # استفاده از ROW_NUMBER برای صفحه‌بندی سازگار با SQL Server نسخه‌های قدیمی
        query = f"""
            WITH DiscountedArticles AS (
                SELECT 
                    A_Code, A_Code_C, A_Name, Sel_Price, Sel_Price10, Exist, Exist2, IsActive, 
                    VahedCode, Rate, Seen, Av_Rate, Image, Tozihat, Karton,
                    ROW_NUMBER() OVER (ORDER BY Sel_Price - Sel_Price10 DESC) AS RowNum
                FROM article
                WHERE Sel_Price10 < Sel_Price AND Sel_Price > 0 AND Sel_Price10 > 0 AND IsActive = 1
            )
            SELECT *
            FROM DiscountedArticles
            WHERE RowNum BETWEEN ? AND ?
        """
        cursor.execute(query, (start_row, end_row))
        articles = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

        articles_list = []
        for row in articles:
            row_dict = dict(zip(columns, row))
            sel_price = float(row_dict["Sel_Price"]) if row_dict["Sel_Price"] else 0
            sel_price10 = float(row_dict["Sel_Price10"]) if row_dict["Sel_Price10"] else 0

            price_diff = sel_price - sel_price10
            discount_percent = (price_diff / sel_price) * 100 if sel_price != 0 else 0
            
            # اگر HideMojoodi فعال باشد، موجودی‌ها را پنهان کن
            if hide_mojoodi:
                row_dict["Exist"] = "تماس بگیرید"
                row_dict["Exist2"] = "تماس بگیرید"


            if vahedpool == "toman":
                sel_price /= 10
                sel_price10 /= 10
                price_diff /= 10

            articles_list.append({
                "A_Code": row_dict["A_Code"],
                "A_Code_C": row_dict["A_Code_C"],
                "A_Name": row_dict["A_Name"],
                "Sel_Price": sel_price,
                "Sel_Price10": sel_price10,
                "Price_Difference": price_diff,
                "Discount_Percentage": discount_percent,
                "Exist": row_dict["Exist"],
                "Exist2": row_dict["Exist2"],
                "IsActive": row_dict["IsActive"],
                "VahedCode": row_dict["VahedCode"],
                "Rate": row_dict["Rate"],
                "Seen": row_dict["Seen"],
                "Av_Rate": row_dict["Av_Rate"],
                "Image": make_image_url(row_dict["A_Code"]),
                "Tozihat": row_dict["Tozihat"] or "",
                "Karton": row_dict["Karton"],
            })

        return jsonify({
            "FldVahedpool": fld_vahedpool_raw,
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
            "Articles": articles_list,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()

            
            
@holoo_bp.route('/tozihat', methods=['POST'])
@require_api_key
def tozihat():
    data = request.get_json()

    if not data or 'a_code' not in data or 'text' not in data:
        return jsonify({'error': 'باید هر دو فیلد را پر کنید'}), 400

    a_code = data['a_code']
    text = data['text']

    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود کالا
        check_query = "SELECT COUNT(*) FROM ARTICLE WHERE A_Code = ?"
        cursor.execute(check_query, (a_code,))
        exists = cursor.fetchone()[0]

        if exists == 0:
            return jsonify({'error': 'محصول مورد نظر وجود ندارد'}), 400

        # بروزرسانی ستون Tozihat
        update_query = "UPDATE ARTICLE SET Tozihat = ? WHERE A_Code = ?"
        cursor.execute(update_query, (text, a_code))
        conn.commit()

        return jsonify({'message': 'توضیحات با موفقیت ثبت شد'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            


@holoo_bp.route('/popular_item', methods=['GET'])
@require_api_key
def popular_item():
    conn = get_article_connection()
    cursor = conn.cursor()

    # پیجینیشن
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    offset = (page - 1) * per_page

    # گرفتن تنظیمات FldVahedpool
    cursor.execute("SELECT TOP 1 FldVahedpool FROM dbo.TblSetting_forooshgahi")
    vahedpool_row = cursor.fetchone()
    vahedpool = vahedpool_row[0] if vahedpool_row else None
    

    # گرفتن لیست محصولات بر اساس بیشترین Seen (محبوب‌ترین‌ها)
    cursor.execute(f"""
        SELECT A_Code, A_Code_c, A_Name, Buy_Price, EndBuy_Price, Sel_Price, Exist, Exist2,
               A_Min, A_Max, First_exist, Exist_Mandeh, FewTakhfif, DarsadTakhfif,
               VahedCode, IsActive, Rate, Seen, Av_Rate, 
               ISNULL(TedadDarkhasti, 0) AS TedadDarkhasti,
               ISNULL(Rate_Count, 0) AS Rate_Count,
               Image,
               Tozihat,
               Karton,
               Sel_Price10
        FROM dbo.ARTICLE
        WHERE IsActive = 1
        ORDER BY Seen DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """, (offset, per_page))
    
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    data = []

    for row in rows:
        item = dict(zip(columns, row))
        
        # محاسبه اختلاف قیمت و درصد
        sel_price = item.get('Sel_Price') or 0
        sel_price10 = item.get('Sel_Price10') or 0
        price_diff = sel_price - sel_price10
        percent_diff = (price_diff / sel_price) * 100 if sel_price else 0

        item['SelPriceDiff'] = round(price_diff, 2)
        item['SelPriceDiffPercent'] = round(percent_diff, 2)
        
        # اگر FldVahedpool برابر با 'toman' است، اختلاف قیمت را به 10 تقسیم کن
        if vahedpool == 'toman':
            item['SelPriceDiff'] = round(item['SelPriceDiff'] / 10, 2)  # تقسیم به 10 برای SelPriceDiff

        # استخراج گروه‌ها از A_Code
        a_code = item['A_Code']
        m_group = a_code[:2]
        s_group = a_code[2:4]

        # گروه اصلی
        cursor.execute("SELECT M_groupname FROM dbo.M_GROUP WHERE M_groupcode = ?", (m_group,))
        m_groupname_row = cursor.fetchone()
        item['M_groupname'] = m_groupname_row[0] if m_groupname_row else ""

        # گروه فرعی
        cursor.execute("""
            SELECT S_groupname FROM dbo.S_GROUP 
            WHERE S_groupcode = ? AND M_groupcode = ?
        """, (s_group, m_group))
        s_groupname_row = cursor.fetchone()
        item['S_groupname'] = s_groupname_row[0] if s_groupname_row else ""

        # تبدیل قیمت به تومان اگر لازم بود
        if vahedpool == 'toman':
            for key in ['Buy_Price', 'EndBuy_Price', 'Sel_Price', 'Sel_Price10']:
                if item[key] is not None:
                    item[key] = float(item[key]) / 10

        # بررسی اشانتیون بودن کالا
        cursor.execute("SELECT 1 FROM dbo.MyGift_WC WHERE A_Code = ?", (a_code,))
        is_gift = cursor.fetchone()
        item['is_gift'] = bool(is_gift)

        data.append(item)

    conn.close()
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total_items": len(data),
        "items": data
    })
    
    
    
    
    
@holoo_bp.route('/with_gift', methods=['GET'])
@require_api_key
def with_gift():
    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # گرفتن تنظیم واحد پول
        cursor.execute("SELECT TOP 1 FldVahedpool FROM dbo.TblSetting_forooshgahi")
        vahedpool_row = cursor.fetchone()
        vahedpool = vahedpool_row[0] if vahedpool_row and vahedpool_row[0] else "rial"

        # پیجینیشن
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        offset = (page - 1) * per_page

        # گرفتن A_Code هایی که is_gift=True هستند
        cursor.execute("SELECT A_Code FROM dbo.MyGift_WC WHERE is_gift = 1")
        gift_codes = [row[0] for row in cursor.fetchall()]

        if not gift_codes:
            return jsonify({"message": "No gift items found", "products": []}), 200

        # محدودسازی به تعداد صفحه فعلی
        page_gift_codes = gift_codes[offset:offset + per_page]
        if not page_gift_codes:
            return jsonify({"message": "No products on this page", "products": []}), 200

        results = []
        for a_code in page_gift_codes:
            cursor.execute("""
                SELECT 
                    A_Code, A_Code_c, A_Name, Buy_Price, EndBuy_Price, Sel_Price, Exist, Exist2,
                    A_Min, A_Max, First_exist, Exist_Mandeh, FewTakhfif, DarsadTakhfif,
                    VahedCode, IsActive, Rate, Seen, Av_Rate,
                    ISNULL(TedadDarkhasti, 0) AS TedadDarkhasti,
                    ISNULL(Rate_Count, 0) AS Rate_Count,
                    Image, Tozihat, Karton, Sel_Price10
                FROM dbo.ARTICLE
                WHERE A_Code = ?
            """, a_code)
            row = cursor.fetchone()

            if row:
                # === گروه کالا
                m_group = a_code[:2]
                s_group = a_code[2:4]

                cursor.execute("SELECT M_groupname FROM dbo.M_GROUP WHERE M_groupcode = ?", (m_group,))
                m_groupname_row = cursor.fetchone()
                m_groupname = m_groupname_row[0] if m_groupname_row else ""

                cursor.execute("""
                    SELECT S_groupname FROM dbo.S_GROUP 
                    WHERE S_groupcode = ? AND M_groupcode = ?
                """, (s_group, m_group))
                s_groupname_row = cursor.fetchone()
                s_groupname = s_groupname_row[0] if s_groupname_row else ""

                # === تبدیل قیمت‌ها اگر واحد تومان باشد
                def adjust_price(val):
                    return round(val / 10, 2) if vahedpool == 'toman' and val else val
                
                # گرفتن قیمت‌های اصلی
                raw_sel_price = row[5]
                raw_sel_price10 = row[24]

                # تبدیل قیمت‌ها در صورت نیاز
                sel_price = adjust_price(raw_sel_price)
                sel_price10 = adjust_price(raw_sel_price10)

                # اختلاف و درصد اختلاف
                sel_price_diff = sel_price - sel_price10
                sel_price_diff_percent = round((sel_price_diff / sel_price) * 100, 2) if sel_price else 0

                result = {
                    "A_Code": row[0],
                    "A_Code_c": row[1],
                    "A_Name": row[2],
                    "Buy_Price": adjust_price(row[3]),
                    "EndBuy_Price": adjust_price(row[4]),
                    "Sel_Price": adjust_price(row[5]),
                    "Exist": row[6],
                    "Exist2": row[7],
                    "A_Min": row[8],
                    "A_Max": row[9],
                    "First_exist": row[10],
                    "Exist_Mandeh": row[11],
                    "FewTakhfif": row[12],
                    "DarsadTakhfif": row[13],
                    "VahedCode": row[14],
                    "IsActive": row[15],
                    "Rate": row[16],
                    "Seen": row[17],
                    "Av_Rate": row[18],
                    "TedadDarkhasti": row[19],
                    "Rate_Count": row[20],
                    "Image": row[21],
                    "Tozihat": row[22],
                    "Karton": row[23],
                    "Sel_Price10": adjust_price(row[24]),
                    "m_group": m_groupname,
                    "s_group": s_groupname,
                    "M_groupcode": m_group,
                    "S_groupcode": s_group,
                    "is_gift": True,
                    "SelPrice_Diff": sel_price_diff,
                    "SelPrice_Diff_Percent": sel_price_diff_percent
                }
                results.append(result)

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_items": len(gift_codes),
            "total_pages": (len(gift_codes) + per_page - 1) // per_page,
            "products": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()



@holoo_bp.route('/add_image_articles', methods=['POST'])
@require_api_key
def add_image_articles():
    # بررسی کنید که درخواست از نوع JSON باشد
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()

    # از صحت وجود a_code و image در داده‌های دریافتی اطمینان حاصل کنید
    a_code = data.get('a_code')
    image_url = data.get('image')

    if not a_code or not image_url:
        return jsonify({"message": "a_code and image are required"}), 400

    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # کوئری برای به‌روزرسانی ستون image در جدول ARTICLE
        # از پارامترهای نام‌گذاری شده (یا ? در SQLite) برای جلوگیری از SQL Injection استفاده کنید.
        sql_query = "UPDATE ARTICLE SET image = ? WHERE a_code = ?"
        cursor.execute(sql_query, (image_url, a_code))
        conn.commit() # تغییرات را ذخیره کنید

        # بررسی کنید که آیا ردیفی به‌روزرسانی شده است یا خیر
        if cursor.rowcount == 0:
            return jsonify({"message": "No article found with the provided a_code"}), 404
        else:
            return jsonify({"message": "Image URL updated successfully", "a_code": a_code, "image_url": image_url}), 200

    except Exception as e:
        # در صورت بروز خطا، آن را لاگ کرده و یک پاسخ خطای عمومی برگردانید
        print(f"Error updating image for a_code {a_code}: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        # مطمئن شوید که اتصال دیتابیس بسته می‌شود
        if conn:
            conn.close()
            
            
            
import os
import requests
from flask import jsonify, request, send_file
from io import BytesIO


@holoo_bp.route('/getgetgetooni', methods=['POST'])
def getgetgetooni():
    data = request.get_json()
    a_code = data.get("a_code")

    if not a_code:
        return jsonify({"status": "error", "message": "کد کالا ارسال نشده است."}), 400

    conn = get_article_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT Image FROM dbo.ARTICLE WHERE A_Code = ?", (a_code,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"status": "error", "message": "کالایی با این کد پیدا نشد."}), 404

        image_url = row[0]

        # اگر عکس آدرس اینترنتی باشد
        if image_url.startswith("http://") or image_url.startswith("https://"):
            response = requests.get(image_url)
            if response.status_code == 200:
                filename = os.path.basename(image_url)
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return send_file(filename, as_attachment=True)
            else:
                return jsonify({"status": "error", "message": "دانلود عکس از اینترنت موفق نبود."}), 400

        # اگر عکس مسیر محلی باشد و فایل وجود داشته باشد
        elif os.path.exists(image_url):
            return send_file(image_url, as_attachment=True)

        else:
            return jsonify({"status": "error", "message": "مسیر فایل معتبر نیست یا فایل موجود نیست."}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


            
            

@holoo_bp.route('/delete_image_articles', methods=['POST'])
@require_api_key
def delete_image_articles():
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    a_code = data.get('a_code')

    if not a_code:
        return jsonify({"message": "a_code is required"}), 400

    try:
        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود کالا و اینکه عکس دارد
        cursor.execute("SELECT image FROM ARTICLE WHERE a_code = ?", (a_code,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"message": "No article found with the provided a_code"}), 404

        current_image = row[0]
        if not current_image:
            return jsonify({"message": "This article does not have an image to delete"}), 400

        # آدرس تصویر پیش‌فرض که قرار است جایگزین شود
        default_image_url = "https://webcomco.com/wp-content/uploads/2025/02/webcomco.com-logo-300x231.webp"

        # بروزرسانی مقدار ستون image
        cursor.execute("UPDATE ARTICLE SET image = ? WHERE a_code = ?", (default_image_url, a_code))
        conn.commit()

        return jsonify({
            "message": "Image removed and replaced with default successfully",
            "a_code": a_code,
            "new_image": default_image_url
        }), 200

    except Exception as e:
        print(f"Error deleting image for a_code {a_code}: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

    finally:
        if conn:
            conn.close()




@holoo_bp.route('/hide_price', methods=['POST'])
@require_api_key
def hide_price():
    """
    ورودی JSON:
    {
    "a_codes": ["123", "456", "789"] # لیست دلخواه کدها
    # یا همچنان:
    # "a_code": "123"
    }

    خروجی JSON نمونه:
    {
    "status": "ok",
    "hidden": ["123", "456"],
    "already_hidden": ["789"],
    "not_found": ["999"]
    }
    """

    # ---------- استخراج ورودی ----------
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "درخواست JSON نامعتبر است."}), 400

    # پشتیبانی از a_code تکی
    if 'a_code' in data:
        a_codes = [str(data['a_code']).strip()]
    else:
        a_codes = data.get('a_codes', [])

    # اعتبارسنجی پایه
    if not isinstance(a_codes, list) or not a_codes:
        return jsonify({"status": "error",
        "message": "کلید a_codes باید یک آرایهٔ غیرخالی باشد."}), 400

    # حذف فضای خالی و فیلتر کدهای خالی
    a_codes = [str(code).strip() for code in a_codes if str(code).strip()]

    # بررسی طول و عددی بودن
    invalid_format = [c for c in a_codes if len(c) > 10 or not c.isdigit()]
    if invalid_format:
        return jsonify({"status": "error",
        "message": f"کدهای نامعتبر (باید عدد و حداکثر 10 رقم باشند): {invalid_format}"}), 400

    # ---------- اتصال به دیتابیس ----------
    conn = get_article_connection()
    cursor = conn.cursor()

    hidden, already_hidden, not_found = [], [], []

    try:
        # همهٔ کدهای موجود در ARTICLE
        placeholders = ','.join(['?'] * len(a_codes))
        cursor.execute(f"SELECT A_Code FROM ARTICLE WHERE A_Code IN ({placeholders})", a_codes)
        existing = {row.A_Code for row in cursor.fetchall()}

        for code in a_codes:
            if code not in existing:
                not_found.append(code)
                continue

            # آیا قبلاً مخفی شده؟
            cursor.execute("SELECT 1 FROM HiddenPrice WHERE A_Code = ?", (code,))
            if cursor.fetchone():
                already_hidden.append(code)
                continue

            # درج در HiddenPrice
            cursor.execute("INSERT INTO HiddenPrice (A_Code) VALUES (?)", (code,))
            hidden.append(code)

        conn.commit()

        return jsonify({
            "status": "ok",
            "hidden": hidden,
            "already_hidden": already_hidden,
            "not_found": not_found
        })

    except Exception as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": f"خطای سرور: {exc}"}), 500
    finally:
        cursor.close()
        conn.close()
        
        


@holoo_bp.route('/dissable_hide_price', methods=['POST'])
@require_api_key
def dissable_hide_price():

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "درخواست JSON نامعتبر است."}), 400

    # حالت تکی یا لیستی
    if 'a_code' in data:
        a_codes = [str(data['a_code']).strip()]
    else:
        a_codes = data.get('a_codes', [])

    if not isinstance(a_codes, list) or not a_codes:
        return jsonify({"status": "error", "message": "کلید a_codes باید یک آرایهٔ غیرخالی باشد یا a_code وارد شود."}), 400

    # حالت خاص: حذف همه موارد پنهان‌شده
    if len(a_codes) == 1 and a_codes[0].lower() == 'all':
        conn = get_article_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM HiddenPrice")
            conn.commit()
            return jsonify({
                "status": "ok",
                "message": "تمام قیمت‌ها دوباره قابل مشاهده شدند."
            })
        except Exception as exc:
            conn.rollback()
            return jsonify({"status": "error", "message": f"خطای سرور: {exc}"}), 500
        finally:
            cursor.close()
            conn.close()

    # ادامه پردازش عادی کدها
    a_codes = [str(code).strip() for code in a_codes if str(code).strip()]

    # اعتبارسنجی فرمت
    invalid_format = [c for c in a_codes if len(c) > 10 or not c.isdigit()]
    if invalid_format:
        return jsonify({"status": "error",
                        "message": f"کدهای نامعتبر (فقط عدد، حداکثر 10 رقم): {invalid_format}"}), 400

    conn = get_article_connection()
    cursor = conn.cursor()
    visible, not_hidden, not_found = [], [], []

    try:
        placeholders = ','.join(['?'] * len(a_codes))
        cursor.execute(f"SELECT A_Code FROM ARTICLE WHERE A_Code IN ({placeholders})", a_codes)
        existing = {row.A_Code for row in cursor.fetchall()}

        for code in a_codes:
            if code not in existing:
                not_found.append(code)
                continue

            cursor.execute("SELECT 1 FROM HiddenPrice WHERE A_Code = ?", (code,))
            if cursor.fetchone() is None:
                not_hidden.append(code)
                continue    

            cursor.execute("DELETE FROM HiddenPrice WHERE A_Code = ?", (code,))
            visible.append(code)

        if visible:
            conn.commit()
            return jsonify({
                "status": "ok",
                "visible": visible,
                "message": "قیمت کالاهای زیر دوباره قابل مشاهده شد."
            })

        # اگر چیزی حذف نشد
        return jsonify({
            "status": "error",
            "message": "هیچ قیمتی برای نمایش یافت نشد.",
            "not_found": not_found,
            "not_hidden": not_hidden
        }), 400

    except Exception as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": f"خطای سرور: {exc}"}), 500
    finally:
        cursor.close()
        conn.close()
        
        
        
@holoo_bp.route('/expire_login', methods=['POST'])
@require_api_key
def expire_login():
    try:
        data = request.get_json()
        if not data or 'mobile' not in data:
            return jsonify({"status": "error", "message": "شماره موبایل ارسال نشده است."}), 400

        mobile = data['mobile']

        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود موبایل در جدول CUSTOMER
        cursor.execute("SELECT C_Code, Login, C_Name, C_Address, C_Mobile, C_Tel FROM CUSTOMER  WHERE C_Mobile = ?", (mobile,))
        customer_row = cursor.fetchone()
        if not customer_row:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "شماره موبایل در سیستم یافت نشد."}), 400

        c_code, login_value, c_name, c_address, c_mobile, c_tel = customer_row

        # واکشی ExpireLogin
        cursor.execute("SELECT ISNULL(ExpireLogin, 0) FROM TblSetting_forooshgahi")
        setting_row = cursor.fetchone()
        expire_login = setting_row[0] if setting_row else 0

        # اگر ExpireLogin فعال بود، بررسی تاریخ آخرین تراکنش
        if expire_login == 1:
            cursor.execute("""
                SELECT MAX(R_Date) 
                FROM RQTITLE 
                WHERE R_CusCode = ?
            """, (c_code,))
            r_date_row = cursor.fetchone()
            last_r_date = r_date_row[0] if r_date_row else None

            if last_r_date:
                from datetime import datetime, timedelta

                if isinstance(last_r_date, str):
                    last_r_date = datetime.strptime(last_r_date, '%Y-%m-%d')

                three_months_ago = datetime.now() - timedelta(days=90)
                if last_r_date < three_months_ago and login_value == 1:
                    # اگر از آخرین تراکنش بیش از ۳ ماه گذشته باشد، Login را به 0 تغییر بده
                    cursor.execute("UPDATE CUSTOMER SET Login = 0 WHERE C_Code = ?", (c_code,))
                    conn.commit()
                    login_value = 0

        cursor.close()
        conn.close()

        return jsonify({
            "status": "ok",
            "C_Code": c_code,
            "Login": bool(login_value),
            "ExpireLogin": bool(expire_login),
            "C_Name": c_name,
            "C_Address": c_address,
            "C_Mobile": c_mobile,
            "C_Tel": c_tel
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



def fetch_best_selling_data(R_Date):
    conn = get_article_connection()
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
        
    
    
@holoo_bp.route("/get_best_selling_articles", methods=["POST"])
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
    
    
    
    
    
from flask import request, jsonify, send_file
import os
import shutil
import urllib.parse
from PIL import Image


from PIL import Image

@holoo_bp.route('/logo', methods=['POST', 'GET'])
@require_api_key
def send_logo():
    try:
        static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "logos"))
        os.makedirs(static_folder, exist_ok=True)

        if request.method == 'GET':
            # گرفتن لوگو از دیتابیس
            conn = get_article_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT Logo FROM TblSetting_forooshgahi")
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row and row.Logo:
                # فرض می‌کنیم Logo URL اصلی ذخیره شده، حالا آدرس دو نسخه کوچک‌تر رو بسازیم
                # مثلا لوگوی اصلی: http://host/static/logos/filename.png
                # نسخه 192: http://host/static/logos/192_filename.png
                # نسخه 512: http://host/static/logos/512_filename.png
                
                base_url = request.host_url.rstrip("/")
                original_url = row.Logo
                filename = os.path.basename(original_url)
                url_192 = f"{base_url}/static/logos/192_{filename}"
                url_512 = f"{base_url}/static/logos/512_{filename}"

                return jsonify({
                    "status": "ok",
                    "logo_original": original_url,
                    "logo_192": url_192,
                    "logo_512": url_512
                })
            else:
                default_logo_url = f"{request.host_url.rstrip('/')}/static/logos/default.png"
                return jsonify({"status": "ok", "logo_url": default_logo_url})

        elif request.method == 'POST':
            if 'logo' not in request.files:
                return jsonify({"status": "error", "message": "فایلی ارسال نشده."}), 400

            file = request.files['logo']

            if file.filename == '':
                return jsonify({"status": "error", "message": "هیچ فایلی انتخاب نشده."}), 400

            allowed_ext = {'png', 'jpg', 'jpeg'}
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext not in allowed_ext:
                return jsonify({"status": "error", "message": "فرمت فایل مجاز نیست."}), 400

            # ذخیره فایل اصلی
            safe_filename = urllib.parse.quote(file.filename)
            dest_path = os.path.join(static_folder, safe_filename)
            file.save(dest_path)

            # ساخت دو نسخه ریسایز شده
            with Image.open(dest_path) as img:
                # نسخه 192x192
                img_192 = img.copy()
                img_192.thumbnail((192, 192))
                img_192.save(os.path.join(static_folder, f"192_{safe_filename}"))

                # نسخه 512x512
                img_512 = img.copy()
                img_512.thumbnail((512, 512))
                img_512.save(os.path.join(static_folder, f"512_{safe_filename}"))

            # ذخیره آدرس اصلی در دیتابیس (آدرس دو نسخه ریسایز شده رو می‌تونیم بر اساس اسم بسازیم)
            base_url = request.host_url.rstrip("/")
            logo_url = f"{base_url}/static/logos/{safe_filename}"

            conn = get_article_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE TblSetting_forooshgahi SET Logo = ?", (logo_url,))
            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({
                "status": "ok",
                "message": "لوگو با موفقیت آپلود و ریسایز شد.",
                "logo_original": logo_url,
                "logo_192": f"{base_url}/static/logos/192_{safe_filename}",
                "logo_512": f"{base_url}/static/logos/512_{safe_filename}"
            })

    except Exception as e:
        return jsonify({"status": "error", "message": f"خطای سرور: {str(e)}"}), 500




@holoo_bp.route('/image_groups', methods=['POST', 'GET'])
@require_api_key
def image_groups():
    try:
        if request.method == 'GET':
            # برگرداندن همه گروه‌ها و URL عکس‌ها
            conn = get_article_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT M_groupcode, Image FROM M_GROUP")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            groups = {row.M_groupcode: row.Image if row.Image else "" for row in rows}

            return jsonify({"status": "ok", "groups": groups})

        elif request.method == 'POST':
            if not request.files:
                return jsonify({"status": "error", "message": "هیچ فایلی ارسال نشده."}), 400

            responses = []

            for groupcode, file in request.files.items():
                # بررسی اینکه گروه موجود است
                conn = get_article_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM M_GROUP WHERE M_groupcode = ?", (groupcode,))
                exists = cursor.fetchone().count
                cursor.close()
                conn.close()

                if not exists:
                    return jsonify({"status": "error", "message": f"گروه اصلی '{groupcode}' وجود ندارد."}), 400

                if file.filename == '':
                    return jsonify({"status": "error", "message": f"هیچ فایلی برای گروه '{groupcode}' انتخاب نشده."}), 400

                # بررسی فرمت
                allowed_ext = {'png', 'jpg', 'jpeg'}
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in allowed_ext:
                    return jsonify({"status": "error", "message": f"فرمت فایل گروه '{groupcode}' مجاز نیست."}), 400

                # مسیر نهایی در static
                static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "group_images"))
                os.makedirs(static_folder, exist_ok=True)
                safe_filename = urllib.parse.quote(file.filename)
                dest_path = os.path.join(static_folder, f"{groupcode}_{safe_filename}")

                # ذخیره فایل
                file.save(dest_path)

                # ساخت URL
                base_url = request.host_url.rstrip("/")
                image_url = f"{base_url}/static/group_images/{groupcode}_{safe_filename}"

                # ذخیره در دیتابیس
                conn = get_article_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE M_GROUP SET Image = ? WHERE M_groupcode = ?", (image_url, groupcode))
                conn.commit()
                cursor.close()
                conn.close()

                responses.append({"M_groupcode": groupcode, "image_url": image_url})

            return jsonify({"status": "ok", "message": "تصاویر گروه با موفقیت آپلود شد.", "uploaded": responses})

    except Exception as e:
        return jsonify({"status": "error", "message": f"خطای سرور: {str(e)}"}), 500



@holoo_bp.route('/s_image_group', methods=['POST', 'GET'])
@require_api_key
def s_image_group():
    try:
        if request.method == 'GET':
            # بازگرداندن همه کدهای ترکیبی و URL تصاویر
            conn = get_article_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT M_groupcode, S_groupcode, Image FROM S_GROUP")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            data = {}
            for row in rows:
                combined = f"{row.M_groupcode}{row.S_groupcode}"
                data[combined] = row.Image if row.Image else ""

            return jsonify({"status": "ok", "data": data})

        # ---------------------- POST ----------------------
        if not request.files:
            return jsonify({"status": "error", "message": "هیچ فایلی ارسال نشده است."}), 400

        # key همون کد هست (مثل 1234)
        code = list(request.files.keys())[0]
        file = request.files[code]

        if len(code) != 4 or not code.isdigit():
            return jsonify({"status": "error", "message": "کد باید عددی 4 رقمی باشد."}), 400

        m_code = code[:2]
        s_code = code[2:]

        if file.filename == '':
            return jsonify({"status": "error", "message": "هیچ فایلی انتخاب نشده است."}), 400

        allowed_ext = {'png', 'jpg', 'jpeg'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[-1].lower() not in allowed_ext:
            return jsonify({"status": "error", "message": "فرمت فایل مجاز نیست. (png/jpg/jpeg)"}), 400

        conn = get_article_connection()
        cursor = conn.cursor()

        # بررسی وجود گروه اصلی و فرعی
        cursor.execute("SELECT COUNT(*) FROM S_GROUP WHERE M_groupcode = ?", (m_code,))
        if cursor.fetchone()[0] == 0:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "گروه اصلی وجود ندارد."}), 400

        cursor.execute("SELECT COUNT(*) FROM S_GROUP WHERE S_groupcode = ?", (s_code,))
        if cursor.fetchone()[0] == 0:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "گروه فرعی وجود ندارد."}), 400

        cursor.execute("SELECT COUNT(*) FROM S_GROUP WHERE M_groupcode = ? AND S_groupcode = ?", (m_code, s_code))
        if cursor.fetchone()[0] == 0:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "ردیف متناظر با این ترکیب یافت نشد."}), 400

        # ذخیره فایل
        static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "s_group_images"))
        os.makedirs(static_folder, exist_ok=True)

        safe_filename = urllib.parse.quote(file.filename)
        final_name = f"{m_code}{s_code}_{safe_filename}"
        dest_path = os.path.join(static_folder, final_name)
        file.save(dest_path)

        # ساخت URL
        base_url = request.host_url.rstrip("/")
        image_url = f"{base_url}/static/s_group_images/{final_name}"

        cursor.execute(
            "UPDATE S_GROUP SET Image = ? WHERE M_groupcode = ? AND S_groupcode = ?",
            (image_url, m_code, s_code)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "ok", "message": "تصویر با موفقیت ثبت شد.", "image_url": image_url, "code": code})

    except Exception as e:
        return jsonify({"status": "error", "message": f"خطای سرور: {str(e)}"}), 500

