# routes/table_initializer.py
import logging
from routes.visitory_erfan import (
    add_image_column_with_default,
    ensure_table_exists,
    ensure_webcom_column_exists,
    ensure_wc_table_exists,
    ensure_visitor_column_exists,
    get_db_connection,
    sync_visitors
)
from routes.holoo import (
    create_and_fill_convert_persian_column,
    create_user_product_rate_table,
    update_customer_persian_column,
    ensure_admin_rate_column_exists,
    ensure_article_rate_column,
    ensure_article_av_rate_column,
    ensure_article_rate_count_column,
    ensure_article_seen_column,
    ensure_article_tedad_darkhasti_column,
    ensure_article_eshantion_column,
    add_image_column_with_default as add_image_router,
    create_tblsetting_forooshgahi,
    create_login_forooshgahi_table,
    create_admin_settip_table,
    add_tozihat_column_if_not_exists,
    create_gift_table_if_not_exists,
    create_mgroup_image_column,
    create_sgroup_image_column,
    add_shomare_card_column,
    create_hidden_price_table,
    hide_exist_column,
    create_customer_login_column,
    add_expirelogin_column,
    add_bit_column_to_settings,
    add_bit_column_hidemojoodi_to_settings,
    add_dtvahed_column,
    add_ttvahed_column,
    add_logo_column
)

from routes.config_utils import load_db_config


def ensure_customer_visitor_table_exists(cursor):
    cursor.execute("""
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
    """)


def ensure_visitor_location_table_exists(cursor):
    cursor.execute("""
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
    """)


def ensure_column_exists(cursor, table_name, column_name, column_type):
    cursor.execute(
        f"""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{column_name}'
        )
        BEGIN
            ALTER TABLE {table_name} ADD {column_name} {column_type}
        END
        """
    )

def alter_column_if_type_differs(cursor, table_name, column_name, expected_data_type):
    cursor.execute(f"""
        SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{column_name}'
    """)
    result = cursor.fetchone()

    if result is None:
        print(f"⚠️ ستون {column_name} در جدول {table_name} یافت نشد.")
        return

    data_type, max_length = result
    current_type = f"{data_type.upper()}({max_length})" if max_length else data_type.upper()
    expected_clean = expected_data_type.upper().replace(" ", "")
    current_clean = current_type.replace(" ", "")

    if expected_clean != current_clean:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} {expected_data_type}")
            print(f"🔁 نوع ستون {column_name} در جدول {table_name} به {expected_data_type} تغییر یافت.")
        except Exception as e:
            print(f"❌ خطا در تغییر نوع ستون {column_name} در جدول {table_name}: {e}")
    else:
        print(f"✅ نوع ستون {column_name} در جدول {table_name} از قبل صحیح است.")

def ensure_column_with_type(cursor, table_name, column_name, expected_data_type):
    # چک کن که ستون وجود دارد یا نه
    cursor.execute(f"""
        SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{column_name}'
    """)
    result = cursor.fetchone()

    if result is None:
        # ستون وجود ندارد → ایجادش کن
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD {column_name} {expected_data_type}")
            print(f"➕ ستون {column_name} با نوع {expected_data_type} در جدول {table_name} اضافه شد.")
        except Exception as e:
            print(f"❌ خطا در اضافه‌کردن ستون {column_name} به جدول {table_name}: {e}")
        return

    # ستون وجود دارد → بررسی کن که نوعش درست است یا نه
    data_type, max_length = result
    current_type = f"{data_type.upper()}({max_length})" if max_length else data_type.upper()
    expected_clean = expected_data_type.upper().replace(" ", "")
    current_clean = current_type.replace(" ", "")

    if expected_clean != current_clean:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} {expected_data_type}")
            print(f"🔁 نوع ستون {column_name} در جدول {table_name} به {expected_data_type} تغییر یافت.")
        except Exception as e:
            print(f"❌ خطا در تغییر نوع ستون {column_name} در جدول {table_name}: {e}")
    else:
        print(f"✅ نوع ستون {column_name} در جدول {table_name} از قبل صحیح است.")


def create_tblsetting_visitori_if_not_exists(cursor):
    cursor.execute("""
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
                WSetTip BIT,
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
                ShowReport BIT,
                SecendTip NVARCHAR(50),
            )
        END
    """)




def setup_all_databases():
    try:
        logging.info("🔧 آماده‌سازی دیتابیس آغاز شد...")

        if load_db_config():
            # Holoo DB
            create_user_product_rate_table()
            create_and_fill_convert_persian_column()
            update_customer_persian_column()
            ensure_admin_rate_column_exists()
            ensure_article_rate_column()
            ensure_article_av_rate_column()
            ensure_article_rate_count_column()
            ensure_article_seen_column()
            ensure_article_tedad_darkhasti_column()
            ensure_article_eshantion_column()
            add_image_router()
            create_tblsetting_forooshgahi()
            create_login_forooshgahi_table()
            create_admin_settip_table()
            add_tozihat_column_if_not_exists()
            create_gift_table_if_not_exists()
            create_mgroup_image_column()
            create_sgroup_image_column()
            add_shomare_card_column()
            create_hidden_price_table()
            hide_exist_column()
            create_customer_login_column()
            add_expirelogin_column()
            add_bit_column_to_settings()
            add_bit_column_hidemojoodi_to_settings()
            add_dtvahed_column()
            add_ttvahed_column()
            add_logo_column()
        else:
            logging.warning("⚠️ اطلاعات اتصال به دیتابیس موجود نیست. از route `/get-user-conn` استفاده کنید.")

        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_column_with_type(cursor, "TblSetting_Visitori", "WSetTip", "BIT")
        ensure_column_with_type(cursor, "TblSetting_Visitori", "SecendTip", "NVARCHAR(50)")
        add_image_column_with_default()
        ensure_visitor_column_exists(conn, "RQTITLE")
        ensure_webcom_column_exists()
        ensure_table_exists(cursor)
        ensure_wc_table_exists(conn, "MyGift_WC")
        ensure_customer_visitor_table_exists(cursor)
        ensure_visitor_location_table_exists(cursor)

        # ستون‌های اضافی RQTITLE و RQDETAIL
        columns_to_ensure = {
            "RQTITLE": [
                ("RqIndex2", "INT NULL"),
                ("RqIndex", "INT NULL"),
                ("RqType", "NVARCHAR(50) NULL"),
                ("R_CusCode", "NVARCHAR(50) NULL"),
                ("R_Date", "DATETIME NULL"),
                ("T_Date", "DATETIME NULL"),
                ("SumPrice", "DECIMAL(18,2) NULL"),
                ("Visitor_Code", "NVARCHAR(50) NULL"),
                ("FactorID", "INT NULL"),
            ],
            "RQDETAIL": [
                ("RqIndex", "INT NULL"),
                ("RqType", "NVARCHAR(50) NULL"),
                ("R_ArCode", "NVARCHAR(50) NULL"),
                ("R_ArName", "NVARCHAR(100) NULL"),
                ("R_Few", "DECIMAL(18,2) NULL"),
                ("R_Cost", "DECIMAL(18,2) NULL"),
            ],
        }

        for table, cols in columns_to_ensure.items():
            for col, col_type in cols:
                ensure_column_exists(cursor, table, col, col_type)

        sync_visitors(cursor)
        conn.commit()

        logging.info("✅ دیتابیس‌ها آماده شدند.")

    except Exception as e:
        logging.error(f"❌ خطا در آماده‌سازی دیتابیس: {e}")

    finally:
        try:
            if "cursor" in locals():
                cursor.close()
            if "conn" in locals():
                conn.close()
        except Exception:
            pass
