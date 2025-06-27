# web_export.py
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
def test_connection(profile_dir: str) -> bool:
    """
    Проверяет, удалось ли открыть Telegram Web с данным профилем.
    Возвращает True, если подключение успешно, иначе False.
    """
    opts = Options()
    opts.add_argument(f"--user-data-dir={profile_dir}")
    try:
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    except Exception as e:
        print("❌ Ошибка запуска Chrome:", e)
        return False

    try:
        driver.get("https://web.telegram.org/k/")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#telegram-app"))
        )
        return True
    except Exception as e:
        print("❌ Ошибка при загрузке Telegram Web:", e)
        return False
    finally:
        driver.quit()

def get_private_channel_link(username: str, profile_dir: str) -> str:
    """
    Открывает web.telegram.org под указанным Chrome-профилем,
    переходит в приватный канал @username и экспортирует ссылку на эфир.
    """
    opts = Options()
    # Укажите путь к профилю, где вы уже залогинились в Telegram Web
    opts.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    wait = WebDriverWait(driver, 15)

    try:
        # 1) Переходим в канал
        driver.get(f"https://web.telegram.org/k/#@{username}")
        # 2) Ждём загрузки панели чата
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.chat-info")))

        # 3) Открываем панель информации
        info_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[aria-label*='Info']")))
        info_btn.click()

        # 4) Кликаем «Voice Chat» или «Video Chat»
        vc_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//span[contains(text(),'Voice Chat') or contains(text(),'Video Chat')]"
        )))
        vc_btn.click()

        # 5) Кликаем «Invite via link» (или «Share link»)
        share_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button//span[contains(text(),'Invite via link') or contains(text(),'Share link')]"
        )))
        share_btn.click()

        # 6) Считываем значение поля input
        link_input = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "input")))
        return link_input.get_attribute("value")

    finally:
        driver.quit()
