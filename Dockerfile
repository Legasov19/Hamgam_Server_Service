# 1. ایمیج پایه
FROM python:3.10-slim

# 2. جلوگیری از سوال پرسیدن در حین نصب پکیج‌ها
ENV DEBIAN_FRONTEND=noninteractive

# 3. نصب تمام نیازمندی‌های سیستمی (با درایور نسخه 18)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gnupg curl ca-certificates && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends unixodbc-dev msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. تنظیم پوشه کاری
WORKDIR /app

# 5. نصب نیازمندی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. کپی کردن سورس کد پروژه
COPY . .

# 7. اعلام کردن پورت اپلیکیشن
EXPOSE 5000

# 8. دستور اجرا در حالت دیباگ برای دیدن هرگونه خطا
CMD ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:5000", "app:app"]