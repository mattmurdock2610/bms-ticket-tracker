import os
import re
import time
import subprocess
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ==================== QUICK SETTINGS ====================
AVENGERS_DATE = "20261220"
DUNE_DATE = "20261216"
THEATRE_NAME = "PVR: Palazzo, The Nexus Vijaya Mall"
# ========================================================

# Pulled securely from GitHub Repository Secrets
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
DEFAULT_CHAT_ID = os.environ["CHAT_ID"]

MOVIES = [
    {
        "name": "Avengers: Doomsday",
        "date": AVENGERS_DATE,
        "theatre": THEATRE_NAME,
        "url": f"https://in.bookmyshow.com/movies/chennai/avengers-doomsday/buytickets/ET00526306/{AVENGERS_DATE}?etCodes=ET00526306&language=english&refEventCode=ET00526306",
        "chat_id": DEFAULT_CHAT_ID,
    },
    {
        "name": "Dune: Part Three",
        "date": DUNE_DATE,
        "theatre": THEATRE_NAME,
        "url": f"https://in.bookmyshow.com/movies/chennai/dune-part-three/buytickets/ET00526290/{DUNE_DATE}?etCodes=ET00526290&language=english&refEventCode=ET00526290",
        "chat_id": DEFAULT_CHAT_ID,
    },
]

def send_alert(message, chat_id=DEFAULT_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
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

def check_single_movie(driver, movie):
    name = movie["name"]
    target_date = movie["date"]
    theatre_name = movie["theatre"]
    target_url = movie["url"]
    chat_id = movie["chat_id"]

    print(f"\n🎬 --- Checking {name} ({target_date}) ---")
    driver.get(target_url)
    time.sleep(15)

    final_url = driver.current_url
    page_title = driver.title
    print(f"📄 Page Title: {page_title}")
    print(f"🔗 Final URL Landed: {final_url}")

    if any(word in page_title.lower() for word in ["attention required", "cloudflare", "just a moment"]):
        print(f"⚠️ Cloudflare blocked the connection for {name}.")
        return False

    if target_date not in final_url:
        print(f"⏳ Redirected! BookMyShow bounced {name} to {final_url}. {target_date} is not open yet.")
        return False

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
    except Exception:
        pass

    target_lower = theatre_name.lower()
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
                f"🚨 *TICKETS ARE OPEN: {name} ({target_date})!* 🚨\n\n"
                f"`{theatre_name}` has started bookings!\n\n"
                f"👉 [Book Now]({target_url})"
            )
            print(f"✅ Found '{theatre_name}' for {name} at scroll step {step}!")
            send_alert(alert_msg, chat_id=chat_id)
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
    print(f"⏳ Scrolled {step + 1} steps. '{theatre_name}' not found for {name} on {target_date}.")
    print(f"📊 Total unique text lines rendered: {len(seen_lines)}")
    print(f"🎬 Sample venues seen: {sample_theatres[:8]}")
    return False

def check_all_movies():
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

        for movie in MOVIES:
            try:
                check_single_movie(driver, movie)
            except Exception as e:
                print(f"⚠️ Error checking {movie['name']}: {e}")
    except Exception as e:
        print(f"⚠️ Browser boot error: {e}")
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
        tracked = "\n".join([f"• *{m['name']}* (`{m['date']}`)" for m in MOVIES])
        send_alert(f"ℹ️ *Hourly Status:* Scanning every 5 mins for `{THEATRE_NAME}`:\n{tracked}")

    check_all_movies()
