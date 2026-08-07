import requests # type: ignore
import firebase_admin # type: ignore
from firebase_admin import credentials # type: ignore
from firebase_admin import firestore # type: ignore
from bs4 import BeautifulSoup # type: ignore
import datetime
import os
import re
import json
from PIL import Image, ImageDraw, ImageFont

# Configuration
SERVICE_ACCOUNTS = [
    "serviceAccount.json",
    "serviceAccountSajek.json"
]

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# goldr.org official public API
GOLDR_API_URL = "https://www.goldr.org/price.js?gttm"
GOLDR_PAGE_URL = "https://www.goldr.org/"
BAJUS_URL = "https://www.bajus.org/gold-price"
LATEST_COLLECTION = "bajush_gold_price"
HISTORY_COLLECTION = "bajush_gold_price_history"

# Bengali digit to ASCII digit mapping
BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def bangla_to_int(text):
    """Converts a Bengali number string like '৳১৮,৯৩৫' to integer 18935."""
    ascii_text = text.translate(BANGLA_DIGITS)
    num_str = re.sub(r"[^\d]", "", ascii_text)
    return int(num_str) if num_str else 0

def create_rate_card_image(rates, output_path="gold_rates.png"):
    """Generates an image with item name, gold rates, and updated date."""
    width, height = 650, 420
    background_color = (20, 24, 33)      # Dark background
    card_color = (32, 38, 50)            # Card box background
    text_gold = (255, 215, 0)            # Gold accent
    text_white = (255, 255, 255)        # Main text
    accent_green = (76, 217, 100)        # Price color

    image = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(image)

    # Outer Card Box
    draw.rounded_rectangle([25, 25, width - 25, height - 25], radius=16, fill=card_color)

    # Fonts
    try:
        title_font = ImageFont.truetype("arial.ttf", 26)
        body_font = ImageFont.truetype("arial.ttf", 20)
        date_font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        title_font = body_font = date_font = ImageFont.load_default()

    # Header Title
    draw.text((50, 45), "BAJUS GOLD PRICE UPDATE", fill=text_gold, font=title_font)
    
    # Updated Date Format: e.g., Date: 07 Aug 2026 | 04:16 PM
    current_time = datetime.datetime.now()
    formatted_date = current_time.strftime("Date: %d %b %Y | %I:%M %p")
    draw.text((50, 85), formatted_date, fill=(180, 190, 205), font=date_font)

    # Separator Line
    draw.line([(50, 115), (width - 50, 115)], fill=(60, 72, 95), width=2)

    # Full Name Mapping
    name_map = {
        "22K": "22 Karat Gold",
        "21K": "21 Karat Gold",
        "18K": "18 Karat Gold",
        "Sonaton": "Traditional Gold (Sonaton)"
    }

    # Draw Items with Name and Price
    y_offset = 135
    gold_data = rates.get("gold", {})
    for key in ["22K", "21K", "18K", "Sonaton"]:
        price = gold_data.get(key)
        if price:
            item_name = name_map.get(key, key)
            # Left: Name
            draw.text((50, y_offset), item_name, fill=text_white, font=body_font)
            # Right: Price
            draw.text((width - 220, y_offset), f"৳ {price:,} / gm", fill=accent_green, font=body_font)
            y_offset += 55

    image.save(output_path)
    return output_path

def send_telegram_notification(rates, image_path=None):
    """Sends dynamic text message and image to Telegram."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[Telegram] Bot token not provided. Skipping notification.")
        return

    gold_data = rates.get("gold", {})
    caption = "🔔 *BAJUS Gold Price Update*\n\n"
    name_map = {
        "22K": "22 Karat Gold",
        "21K": "21 Karat Gold",
        "18K": "18 Karat Gold",
        "Sonaton": "Traditional Gold"
    }

    for key in ["22K", "21K", "18K", "Sonaton"]:
        if key in gold_data:
            caption += f"• *{name_map.get(key, key)}:* ৳{gold_data[key]:,}/gm\n"

    caption += f"\n📅 _Date: {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}_"

    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(image_path, "rb") as img_file:
                payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
                files = {"photo": img_file}
                res = requests.post(url, data=payload, files=files, timeout=15)
                res.raise_for_status()
            print("Telegram photo message sent successfully!")
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": caption, "parse_mode": "Markdown"}
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            print("Telegram text message sent successfully!")
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def fetch_from_goldr_api():
    """Fallback: goldr.org official public API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.goldr.org/",
        "Accept": "*/*"
    }
    try:
        response = requests.get(GOLDR_API_URL, headers=headers, timeout=15)
        response.raise_for_status()

        match = re.search(
            r"const\s+GoldrPriceTable_goldData\s*=\s*(\[.*?\])\s*;",
            response.text, re.DOTALL
        )
        if not match:
            print("Error: Could not locate GoldrPriceTable_goldData in API response.")
            return None

        feed = json.loads(match.group(1))
        key_order = ["22K", "21K", "18K", "Sonaton"]

        rates = {"gold": {}}
        for i, item in enumerate(feed):
            if i < len(key_order):
                price = int(round(item.get("bg_raw", 0)))
                if price > 0:
                    rates["gold"][key_order[i]] = price

        if len(rates["gold"]) == 4:
            print("Successfully fetched rates from goldr.org official API.")
            return rates
        else:
            print(f"goldr.org API parsing incomplete (found {len(rates['gold'])} karats).")
            return None
    except Exception as e:
        print(f"Error fetching from goldr.org API: {e}")
        return None

def fetch_from_goldr_html():
    """Fallback: Scrapes goldr.org HTML page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    }
    try:
        response = requests.get(GOLDR_PAGE_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        gram_div = soup.find("div", id="table-gram")
        if not gram_div:
            print("Error: Could not find gram price table on goldr.org HTML.")
            return None

        table = gram_div.find("table")
        if not table:
            print("Error: Could not find gold table in gram section.")
            return None

        karat_map = {
            "22 Karat Gold": "22K",
            "21 Karat Gold": "21K",
            "18 Karat Gold": "18K",
            "Traditional": "Sonaton"
        }

        rates = {"gold": {}}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            for karat_text, key in karat_map.items():
                if karat_text in label and key not in rates["gold"]:
                    strong = cells[1].find("strong")
                    if strong:
                        price = bangla_to_int(strong.get_text(strip=True))
                        if price > 0:
                            rates["gold"][key] = price

        if len(rates["gold"]) == 4:
            print("Fetched rates from goldr.org HTML page.")
            return rates
        else:
            print(f"goldr.org HTML parsing incomplete (found {len(rates['gold'])} karats).")
            return None
    except Exception as e:
        print(f"Error fetching from goldr.org HTML: {e}")
        return None

def fetch_from_bajus():
    """Last fallback: Official BAJUS website."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    try:
        response = requests.get(BAJUS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        mapping = {"22 KARAT": "22K", "21 KARAT": "21K", "18 KARAT": "18K", "TRADITIONAL": "Sonaton"}

        rates = {"gold": {}}
        for row in soup.find_all("tr"):
            text = row.get_text()
            if "Gold" in text or "GOLD" in text or "TRADITIONAL" in text or "Traditional" in text:
                for keyword, key in mapping.items():
                    if keyword in text and key not in rates["gold"]:
                        cells = row.find_all(["td", "th"])
                        for cell in cells:
                            cell_str = cell.get_text(strip=True)
                            if "BDT" in cell_str or "GRAM" in cell_str:
                                num_str = re.sub(r"[^\d]", "", cell_str)
                                if num_str:
                                    rates["gold"][key] = int(num_str)

        if len(rates["gold"]) == 4:
            print("Fetched rates from BAJUS (bajus.org).")
            return rates
        else:
            print(f"BAJUS parsing incomplete (found {len(rates['gold'])} karats).")
            return None
    except Exception as e:
        print(f"Error fetching from BAJUS: {e}")
        return None

def get_gold_rates():
    """Fetches gold rates with 3-source fallback chain."""
    rates = fetch_from_goldr_html()
    if not rates:
        rates = fetch_from_goldr_api()
    if not rates:
        rates = fetch_from_bajus()

    if rates:
        print("--- Gold Rates ---")
        for key in ["22K", "21K", "18K", "Sonaton"]:
            if key in rates["gold"]:
                print(f"{key} {rates['gold'][key]}")
    return rates

def update_firestore(new_rates, account_path, app_name):
    """Updates Firestore if data has changed."""
    if not os.path.exists(account_path):
        print(f"\n[Dry Run] Database update skipped ({account_path} missing).")
        return False

    app = None
    has_changed = False
    try:
        cred = credentials.Certificate(account_path)
        app = firebase_admin.initialize_app(cred, name=app_name)
        db = firestore.client(app=app)

        latest_ref = db.collection(LATEST_COLLECTION).document('latest')
        latest_doc = latest_ref.get()

        current_data = latest_doc.to_dict() if latest_doc.exists else {}

        if not current_data:
            has_changed = True
        else:
            if 'gold' in new_rates:
                if 'gold' not in current_data:
                    has_changed = True
                else:
                    curr_gold = current_data['gold'] # type: ignore
                    new_gold = new_rates['gold'] # type: ignore
                    for karat, price in new_gold.items():
                        if curr_gold.get(karat) != price:
                            has_changed = True
                            break

        if has_changed:
            print(f"\nPrice updated for {account_path}. Writing to Firestore...")
            import copy
            data_to_save = copy.deepcopy(new_rates)
            timestamp = datetime.datetime.now(datetime.timezone.utc)
            data_to_save['fetchedAt'] = timestamp

            latest_ref.set(data_to_save)
            print(f"Updated 'latest' for {account_path}.")

            history_ref = db.collection(HISTORY_COLLECTION).document(timestamp.isoformat())
            history_ref.set(data_to_save)
            print(f"Archived to history for {account_path}.")
        else:
            print(f"\nNo change in prices for {account_path}.")

    except Exception as e:
        print(f"Error updating Firestore for {account_path}: {e}")
    finally:
        if app:
            firebase_admin.delete_app(app)

    return has_changed

if __name__ == "__main__":
    rates = get_gold_rates()
    if rates:
        any_price_updated = False
        for i, account in enumerate(SERVICE_ACCOUNTS):
            print(f"\n--- Checking account [{i+1}/{len(SERVICE_ACCOUNTS)}]: {account} ---")
            updated = update_firestore(rates, account, app_name=f"app_{i}")
            if updated:
                any_price_updated = True

        if any_price_updated:
            print("\nGenerating rate card image and sending Telegram alert...")
            image_path = create_rate_card_image(rates)
            send_telegram_notification(rates, image_path=image_path)
            
            if os.path.exists(image_path):
                os.remove(image_path)
    else:
        print("Failed to get rates.")