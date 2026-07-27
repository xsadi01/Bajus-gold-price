from datetime import datetime
import json
import os
import re
import sys
import time
from PIL import Image, ImageDraw, ImageFont
import firebase_admin
from firebase_admin import credentials, db
import pytz
import requests

# --- ১. পরিবেশের ভেরিয়েবল ও কনফিগারেশন ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "xsadi01/Bajus-gold-price")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_PRICE_FILE = os.path.join(SCRIPT_DIR, "last_price.json")
SERVICE_ACCOUNT_FILE = os.path.join(SCRIPT_DIR, "serviceAccountKey.json")

# ফাইল পাথ
THERMAL_IMAGE_FILE = os.path.join(SCRIPT_DIR, "thermal_print.png")
COLOR_IMAGE_FILE = os.path.join(SCRIPT_DIR, "color_price.png")

TARGET_URL = "https://www.goldr.org/price.js?gttm"

# নাম ছোট করার ম্যাপ
NAME_MAPPING = {
    "২২ ক্যারেট সোনার দাম": "22K-",
    "২১ ক্যারেট সোনার দাম": "21K-",
    "১৮ ক্যারেট সোনার দাম": "18K-",
    "সনাতন পদ্ধতির সোনার দাম": "SAN-",
}

# --- ২. ফায়ারবেস সেটআপ ---
if os.path.exists(SERVICE_ACCOUNT_FILE):
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
        firebase_admin.initialize_app(
            cred,
            {
                "databaseURL": "https://cal-by-sss-default-rtdb.asia-southeast1.firebasedatabase.app/"
            },
        )
        print("✅ Firebase Initialized.")
    except Exception as e:
        print(f"⚠️ Firebase initialization failed: {e}")
else:
    print(f"⚠️ {SERVICE_ACCOUNT_FILE} not found. Skipping Firebase setup.")


# --- ৩. ডেটা ফেচিং ---
def get_latest_market_data():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(TARGET_URL, headers=headers, timeout=10)
        js_content = response.text

        gold_match = re.search(
            r"GoldrPriceTable_goldData\s*=\s*(\[[\s\S]*?\]);", js_content
        )
        date_match = re.search(r'const datetime\s*=\s*"([^"]+)"', js_content)

        if not gold_match:
            raise Exception("Format not found")

        gold_data = json.loads(gold_match[1])

        update_date = datetime.now().strftime("%Y-%m-%d")
        if date_match and date_match.group(1):
            update_date = date_match.group(1).split(" ")[0]

        return {"goldData": gold_data, "updateDate": update_date}
    except Exception as error:
        print(f"Data error: {error}")
        return None


# --- ৪. ফায়ারবেসে ডেটা সেভ করার ফাংশন ---
def save_to_firebase(data):
    if not firebase_admin._apps:
        return

    try:
        results = {}
        for item in data["goldData"]:
            raw_name = item.get("n", "")
            name = NAME_MAPPING.get(raw_name, raw_name).replace("-", "")
            if name == "SAN":
                name = "TRADITIONAL"

            bg_raw = float(item.get("bg_raw", 0))
            results[name] = str(int(bg_raw))

        dhaka_tz = pytz.timezone("Asia/Dhaka")
        bd_time = datetime.now(dhaka_tz).strftime("%d/%m/%Y, %I:%M %p").lower()

        final_data = {
            "last_updated": bd_time,
            "prices": results,
            "status": "Live",
        }

        ref = db.reference("gold_data")
        ref.set(final_data)
        print("✅ Firebase Updated:", results)
    except Exception as e:
        print(f"❌ Firebase Update Error: {e}")


def get_bold_font(font_size):
    font_paths = [
        "arialbd.ttf",
        "ariblk.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, font_size)
        except IOError:
            continue
    return ImageFont.load_default()


# --- ৫. থার্মাল ইমেজ জেনারেটর ---
def generate_thermal_image(data):
    width = 384
    height = 256

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = get_bold_font(44)

    current_y = 10

    for item in data["goldData"]:
        raw_name = item.get("n", "")
        name = NAME_MAPPING.get(raw_name, raw_name)

        bg_raw = float(item.get("bg_raw", 0))
        g_price = f"{bg_raw:,.0f}"

        draw.text((10, current_y), name, fill=(0, 0, 0), font=font)

        right_text = f"{g_price} TK"
        bbox = font.getbbox(right_text)
        text_width = bbox[2] - bbox[0]
        x_right = width - 10 - text_width

        draw.text((x_right, current_y), right_text, fill=(0, 0, 0), font=font)
        current_y += 62

    img.save(THERMAL_IMAGE_FILE)
    print("Thermal image generated.")


# --- ৬. স্বচ্ছ কালার ইমেজ জেনারেটর (Zoomed / Enlarged) ---
def generate_color_image(data):
    width = 1000
    height = 667

    img = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = get_bold_font(150)

    RED_COLOR = (255, 0, 0, 255)
    GREEN_COLOR = (0, 230, 0, 255)

    current_y = 5

    for item in data["goldData"]:
        raw_name = item.get("n", "")
        name = NAME_MAPPING.get(raw_name, raw_name)

        bg_raw = float(item.get("bg_raw", 0))
        g_price = f"{bg_raw:,.0f}"

        draw.text((0, current_y), name, fill=RED_COLOR, font=font)

        bbox = font.getbbox(g_price)
        text_width = bbox[2] - bbox[0]
        x_right = width - text_width

        draw.text((x_right, current_y), g_price, fill=GREEN_COLOR, font=font)

        current_y += 162

    img.save(COLOR_IMAGE_FILE, "PNG")
    print("Zoomed Transparent Color image generated successfully.")


# --- ৭. টেলিগ্রাম নোটিফিকেশন ---
def send_telegram_notification(message, color_image_url, thermal_image_url):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram tokens missing. Skipping message send.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🖼️ Transparent Image", "url": color_image_url},
                    {"text": "🖨️ Thermal Image", "url": thermal_image_url},
                ]
            ]
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Notification sent.")
    except Exception as error:
        print(f"Telegram error: {error}")


# --- ৮. মেইন এক্সিকিউশন ---
def run():
    current_data = get_latest_market_data()
    if not current_data:
        return

    # ১. ফায়ারবেসে ডেটা সেভ
    save_to_firebase(current_data)

    # ২. দুটি ইমেজ জেনারেট
    generate_thermal_image(current_data)
    generate_color_image(current_data)

    old_data = None
    if os.path.exists(LAST_PRICE_FILE):
        try:
            with open(LAST_PRICE_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            old_data = None

    if old_data and current_data.get("goldData") == old_data.get("goldData"):
        print(
            "No price change detected. Images updated but skipping telegram alert."
        )
        return

    message = f"🔔 *GOLD PRICE UPDATED*\n"
    message += f"📅 `{current_data['updateDate']}`\n\n"
    message += f"`Type    | Per Gram | Per Vori `\n"
    message += f"`-------------------------------`\n"

    for item in current_data["goldData"]:
        raw_name = item.get("n", "")
        name = NAME_MAPPING.get(raw_name, raw_name)
        clean_name = name.replace("-", "").ljust(6)

        bg_raw = float(item.get("bg_raw", 0))
        bv_raw = float(item.get("bv_raw", 0))

        g_price = f"{bg_raw:,.0f}".ljust(6)
        v_price = f"{bv_raw:,.0f}".ljust(6)

        message += f"`{clean_name} | {g_price} | {v_price} ৳`\n"

    timestamp = int(time.time() * 1000)
    color_image_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/color_price.png?t={timestamp}"
    thermal_image_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/thermal_print.png?t={timestamp}"

    send_telegram_notification(message, color_image_url, thermal_image_url)

    with open(LAST_PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()