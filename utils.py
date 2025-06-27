# utils.py

import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def test_connection(profile_path: str) -> bool:
    try:
        options = Options()
        options.add_argument(f"user-data-dir={os.path.abspath(profile_path)}")
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(10)
        driver.get("https://web.telegram.org/k/")
        success = "telegram" in driver.title.lower() or "логин" not in driver.page_source.lower()
        driver.quit()
        return success
    except Exception as e:
        print("Ошибка при проверке Telegram Web:", e)
        return False
