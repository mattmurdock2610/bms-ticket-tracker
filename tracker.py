import os
import re
import time
import subprocess
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ==================== CONFIGURATION ====================
TARGET_DATE = "20261220"
TARGET_URL = f"https://in.bookmyshow.com/movies/chennai/avengers-doomsday/buytickets/ET00526306/{TARGET_DATE}?etCodes=ET00526306&language=english&refEventCode=ET00526306"
THEATRE_NAME = "PVR: Palazzo, The Nexus Vijaya Mall"

# Pulled securely from GitHub Repository Secrets
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
# =======================================================

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print("🚀 Telegram alert sent successfully!")
        else:
            print(f"❌ Failed to send Telegram alert: {response.text}")
    except Exception as e:
        print(f"❌ Network error: {e}")

def get_chrome_major_version():
    try:
        output = subprocess.check_output(["google-chrome", "--version"], text=True)
        match = re.search(r"(\d+)\.", output)
        if match:
            version = int(match.group(1))
            print(f"🔎 Detected Chrome major version: {version}")
            return version
    except Exception as e:
        print(f"⚠️ Could not auto-detect Chrome version ({e}), defaulting to 157.")
    return 157

def check_booking_status():
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--proxy-server=socks5://127.0.0.1:40000')

    driver = None
    try:
        chrome_ver = get_chrome_major_version()
        print(f"[{time.strftime('%H:%M:%S')}] Booting Stealth Browser (v{chrome_ver}) via WARP...")
        driver = uc.Chrome(options=options, version_main=chrome_ver)

        driver.get(TARGET_URL)
        time.sleep(15)

        final_url = driver.current_url
        page_title = driver.title
        print(f"📄 Page Title: {page_title}")
        print(f"🔗 Final URL Landed: {final_url}")

        if any(word in page_title.lower() for word in ["attention required", "cloudflare", "just a moment"]):
            print("⚠️ Cloudflare blocked the connection.")
            return False

        if TARGET_DATE not in final_url:
            print(f"⏳ Redirected! BookMyShow bounced us to {final_url}. {TARGET_DATE} is not open yet.")
            return False

        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
        except Exception:
            pass

        target_lower = THEATRE_NAME.lower()
        seen_lines = set()
        last_scroll_y = -1
        stuck_count = 0

        for step in range(100):
            raw_text = driver.find_element(By.TAG_NAME, "body").text
            normalized_text = re.sub(r'\s+', ' ', raw_text)

            for line in raw_text.splitlines():
                clean_line = line.strip()
                if clean_line:
                    seen_lines.add(clean_line)

            if target_lower in normalized_text.lower():
                alert_msg = (
                    f"🚨 *TICKETS ARE OPEN FOR {TARGET_DATE}!* 🚨\n\n"
                    f"`{THEATRE_NAME}` has started bookings!\n\n"
                    f"👉 [Book Now]({TARGET_URL})"
                )
                print(f"✅ Found '{THEATRE_NAME}' at scroll step {step}!")
                send_alert(alert_msg)
                return True

            driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(1)

            current_y = driver.execute_script("return window.scrollY;")
            if current_y == last_scroll_y:
                stuck_count += 1
                if stuck_count >= 3:
                    break
            else:
                stuck_count = 0
            last_scroll_y = current_y

        sample_theatres = [l for l in seen_lines if any(k in l.lower() for k in ["pvr", "inox", "ags", "multiplex", "cinemas", "mall"])]
        print(f"⏳ Scrolled {step + 1} steps. '{THEATRE_NAME}' not found for {TARGET_DATE}.")
        print(f"📊 Total unique text lines rendered: {len(seen_lines)}")
        print(f"🎬 Sample venues seen: {sample_theatres[:8]}")
        return False

    except Exception as e:
        print(f"⚠️ Browser error: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    print("🤖 Cloud Monitor: Running scheduled check...")

    utc_minute = int(time.strftime('%M', time.gmtime()))
    ist_minute = (utc_minute + 30) % 60
    if ist_minute < 5:
        send_alert(f"ℹ️ *Hourly Status:* Scanning every 5 mins for `{THEATRE_NAME}` on `{TARGET_DATE}`!")

    check_booking_status()
