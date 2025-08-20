import os
import time
import requests
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

def download_image(image_url: str, folder: str, query: str) -> str | None:
    # (این تابع بدون تغییر باقی می‌ماند)
    if not image_url: return None
    try:
        print(f"در حال دانلود عکس از:\n{image_url}")
        response = requests.get(image_url, stream=True, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        content_type = response.headers.get('content-type')
        extension = '.jpg'
        if content_type:
            if 'image/jpeg' in content_type: extension = '.jpg'
            elif 'image/png' in content_type: extension = '.png'
            elif 'image/webp' in content_type: extension = '.webp'
        safe_filename = "".join(c for c in query if c.isalnum() or c in " _-").rstrip()
        filename = f"{safe_filename[:50]}_{int(time.time())}{extension}"
        file_path = os.path.join(folder, filename)
        os.makedirs(folder, exist_ok=True)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(8192): f.write(chunk)
        print(f"عکس با موفقیت در مسیر زیر ذخیره شد:\n{file_path}")
        return file_path
    except requests.exceptions.RequestException as e:
        print(f"خطا در هنگام دانلود عکس: {e}")
        return None

def fetch_and_download_with_smart_wait(query: str):
    """
    با استفاده از یک انتظار هوشمند برای ظاهر شدن اولین تصویر در پنل،
    عکس با کیفیت را پیدا و دانلود می‌کند.
    """
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch"

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
    
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        try:
            print(f"در حال جستجو برای: '{query}'...")
            driver.get(search_url)
            # زمان انتظار را کمی بیشتر می‌کنیم
            wait = WebDriverWait(driver, 25)

            try:
                accept_button_xpath = "//button[.//div[contains(text(), 'پذیرفتن همه')]]"
                accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, accept_button_xpath)))
                accept_button.click()
                print("کادر کوکی پذیرفته شد.")
            except TimeoutException:
                print("کادر کوکی پیدا نشد، ادامه می‌دهیم...")

            thumbnails = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.H8Rx8c")))
            thumbnails[0].click()
            print("روی اولین تصویر کلیک شد. در حال انتظار برای ظاهر شدن تصاویر در پنل...")

            # --- مرحله کلیدی: انتظار هوشمند برای اولین تصویر در پنل ---
            # ما منتظر می‌مانیم تا اولین تگ 'img' در داخل پنل دیالوگ ظاهر شود.
            # این تضمین می‌کند که پنل خالی نیست.
            first_image_in_panel_xpath = "//div[@role='dialog']//img"
            wait.until(EC.presence_of_element_located((By.XPATH, first_image_in_panel_xpath)))
            
            print("تصاویر در پنل ظاهر شدند. در حال بررسی برای یافتن بزرگترین عکس...")
            # یک مکث بسیار کوتاه برای اینکه بقیه تصاویر هم فرصت بارگذاری داشته باشند
            time.sleep(2)

            dialog_panel = driver.find_element(By.XPATH, "//div[@role='dialog']")
            images_in_panel = dialog_panel.find_elements(By.TAG_NAME, "img")
            
            best_url = None
            max_area = 0
            
            print(f"تعداد {len(images_in_panel)} تصویر در پنل پیدا شد. در حال بررسی...")

            for img in images_in_panel:
                try:
                    src = img.get_attribute("src")
                    if src and src.startswith("http"):
                        width = img.size.get('width', 0)
                        height = img.size.get('height', 0)
                        area = width * height
                        if area > max_area:
                            max_area = area
                            best_url = src
                except Exception:
                    continue
            
            if best_url:
                print(f"بزرگترین عکس با ابعاد {max_area} پیکسل پیدا شد.")
                download_image(image_url=best_url, folder="downloads", query=query)
            else:
                print("\nمتاسفانه هیچ عکس معتبری در پنل برای دانلود پیدا نشد.")

        except TimeoutException:
            print("خطای Timeout: در زمان مشخص شده، هیچ تصویری در پنل پیش‌نمایش ظاهر نشد.")
        except Exception as e:
            print(f"یک خطای پیش‌بینی نشده در فرآیند Selenium رخ داد: {e}")

if __name__ == "__main__":
    product_name = "گوشی موبایل اپل مدل iPhone 15 Pro Max"
    fetch_and_download_with_smart_wait(product_name)