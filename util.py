import yaml
import requests
import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options


# ✅ Load Configuration from YAML
def load_config():
    with open("config.yml", "r") as file:
        return yaml.safe_load(file)


CONFIG = load_config()

# ✅ Set up logging
logging.getLogger('seleniumwire').setLevel(logging.WARNING)

# ✅ Config Variables
CITY = CONFIG["settings"]["city"]
COUNTRY = CONFIG["settings"]["country"]
METHOD = CONFIG["settings"]["method"]
LIVESTREAM_URL = CONFIG["livestream"]["url"]
AUTO_UNMUTE = CONFIG["livestream"]["auto_unmute"]
BROWSER = CONFIG["livestream"]["browser"]
WAIT_TIME = CONFIG["livestream"]["wait_time"]

from typing import Optional


def get_m3u8_url(page_url: str) -> Optional[str]:
    """
    Opens the livestream page and captures the first .m3u8 URL request.
    Uses selenium-wire to intercept network requests, supports Chrome or Brave.
    Returns the valid .m3u8 link if found, otherwise None.
    """

    logging.info(f"🌍 Launching browser to capture livestream requests for: {page_url}")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")

    # Choose browser based on config
    if BROWSER.lower() == "brave":
        chrome_options.binary_location = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(page_url)
        logging.info("⏳ Waiting for livestream to load and network requests to start...")

        # Wait longer than before for stream initialization
        time.sleep(WAIT_TIME + 5)

        m3u8_url = None
        for request in driver.requests:
            if request.response and ".m3u8" in request.url:
                m3u8_url = request.url
                break

        if m3u8_url:
            logging.info(f"✅ Found M3U8 URL: {m3u8_url}")
            return m3u8_url
        else:
            logging.warning("⚠️ No M3U8 URL found. The stream may not have started yet.")
            return None

    except Exception as e:
        logging.exception(f"❌ Error while fetching M3U8 URL: {e}")
        return None
    finally:
        driver.quit()


def get_prayer_times():
    """
    Fetches prayer times from Aladhan API based on the config settings.
    Converts them into datetime.time objects.
    """
    api_url = f"https://api.aladhan.com/v1/timingsByCity?city={CITY}&country={COUNTRY}&method={METHOD}"
    logging.info(f"🕌 Fetching prayer times for {CITY}, {COUNTRY}...")

    response = requests.get(api_url, timeout=10000)
    data = response.json()

    if response.status_code == 200:
        return {
            name: datetime.strptime(time_str, "%H:%M").time()
            for name, time_str in data["data"]["timings"].items()
        }
    else:
        logging.error("⚠️ Error fetching prayer times!")
        return None


def unmute_video():
    """
    Opens the livestream page, switches to the iframe, continuously hovers over the video,
    and clicks the correct mute button if auto_unmute is enabled.
    """
    if not AUTO_UNMUTE:
        logging.info("🔕 Auto-unmute is disabled in config. Skipping...")
        return

    logging.info("🚀 Starting the Chrome driver...")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    # ✅ Start WebDriver
    driver = webdriver.Chrome(options=options)

    logging.info("🌍 Opening the livestream page...")
    driver.get(LIVESTREAM_URL)

    try:
        logging.info("⏳ Waiting for the iframe to load...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)
        logging.info("📺 Switched to the video iframe.")

        logging.info("⏳ Waiting for the video element to appear...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        video_element = driver.find_element(By.TAG_NAME, "video")

        logging.info("🎥 Starting continuous hover loop...")
        actions = ActionChains(driver)

        for _ in range(5):  # Try hovering 5 times
            actions.move_to_element(video_element).perform()
            logging.info("🎥 Hovering over the video...")
            time.sleep(1)

            try:
                logging.info("🔍 Looking for the mute button...")
                mute_button = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "drawer-icon.media-control-icon"))
                )
                logging.info("✅ Mute button found!")
                mute_svg = mute_button.find_element(By.TAG_NAME, "svg")
                mute_svg.click()
                logging.info("🎉 Stream unmuted successfully!")
                break
            except Exception:
                logging.warning("⚠️ Mute button not found. Retrying hover...")

    except Exception as e:
        logging.exception("❌ An error occurred during execution.")

    logging.info("🎥 Browser will remain open. Verify if audio is playing.")
