import os
import fitz  # PyMuPDF
import datetime
import requests
from telegram import Bot
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import threading
import time
import logging

# --- Basic logging setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === CONFIG ===
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    CHAT_ID = os.environ["CHAT_ID"]
except KeyError as e:
    logging.critical(f"FATAL: Environment variable {e} not set. The application cannot start.")
    exit()

GITHUB_PDF_URL = 'https://github.com/farhathkkk/acju-prayer-times/raw/main/Prayer-Times-{month}-{year}-COLOMBO.pdf'
LOCAL_PDF = 'today.pdf'
SELF_URL = os.getenv("SELF_URL")  # e.g., https://your-app.onrender.com

bot = Bot(token=BOT_TOKEN)

def download_pdf(target_date):
    month = target_date.strftime('%B')
    year = target_date.year
    url = GITHUB_PDF_URL.format(month=month, year=year)
    
    logging.info(f"Downloading PDF from {url}")
    try:
        response = requests.get(url, timeout=15)
        # Raise an exception if the download failed (e.g., 404 Not Found)
        response.raise_for_status()
        with open(LOCAL_PDF, 'wb') as f:
            f.write(response.content)
        logging.info("PDF downloaded successfully.")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download PDF. Error: {e}")
        return False

def extract_tomorrows_prayers(tomorrow_date):
    try:
        doc = fitz.open(LOCAL_PDF)
    except fitz.errors.FitzError as e:
        logging.error(f"Could not open or read the PDF file '{LOCAL_PDF}'. It may be corrupted. Error: {e}")
        return None, tomorrow_date

    # Use a format that works across different operating systems
    tomorrow_str = tomorrow_date.strftime('%#d-%b' if os.name == 'nt' else '%-d-%b')

    for page in doc:
        lines = page.get_text("text").split('\n')
        for i, line in enumerate(lines):
            cleaned_line = line.strip()
            # Find the line that starts with the date
            if cleaned_line.startswith(tomorrow_str):
                # Assume the times are on the same line
                if len(cleaned_line.split()) > 5:
                    return cleaned_line, tomorrow_date
                # If not, assume the times are on the next non-empty line
                elif i + 1 < len(lines):
                    for next_line in lines[i+1:]:
                        if next_line.strip():
                            return f"{cleaned_line} {next_line.strip()}", tomorrow_date
    return None, tomorrow_date

def send_daily_prayers():
    try:
        logging.info("Running send_daily_prayers job...")
        colombo_tz = pytz.timezone("Asia/Colombo")
        tomorrow = datetime.datetime.now(colombo_tz) + datetime.timedelta(days=1)
        
        if not download_pdf(tomorrow):
            bot.send_message(chat_id=CHAT_ID, text="🚨 Alert: Failed to download the prayer times PDF.")
            return

        raw, t_date = extract_tomorrows_prayers(tomorrow)
        if not raw:
            logging.error("No prayer time found after parsing PDF.")
            bot.send_message(chat_id=CHAT_ID, text=f"🔍 Alert: Could not find prayer times for {tomorrow.strftime('%d-%b')} in the PDF.")
            return

        parts = raw.split()
        if len(parts) < 13:
            logging.error(f"Line format error. Expected 13+ parts, but got {len(parts)}: '{raw}'")
            bot.send_message(chat_id=CHAT_ID, text=f"📄 Alert: Found the line for tomorrow, but the format was incorrect: `{raw}`")
            return

        date_str = t_date.strftime("%A, %d %B %Y")
        msg = (
            f"🕌 *Prayer Times - Colombo, Sri Lanka*\n"
            f"📅 *{date_str}*\n\n"
            f" Fajr\t\t\t- {parts[1]} {parts[2]}\n"
            f" Sunrise\t- {parts[3]} {parts[4]}\n"
            f" Luhar\t\t- {parts[5]} {parts[6]}\n"
            f" Asar\t\t\t- {parts[7]} {parts[8]}\n"
            f" Maghrib\t- {parts[9]} {parts[10]}\n"
            f" Isha\t\t\t- {parts[11]} {parts[12]}\n\n"
            f"Source: ACJU"
        )

        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        logging.info("Message sent successfully.")

    except Exception as e:
        logging.critical(f"An unexpected error occurred in send_daily_prayers: {e}", exc_info=True)
        try:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 **BOT ERROR** 🚨\n\nThe bot ran into a critical error: `{e}`")
        except Exception as telegram_error:
            logging.error(f"Could not send the error notification to Telegram: {telegram_error}")

# === APScheduler Setup ===
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Colombo"))
scheduler.add_job(send_daily_prayers, trigger='cron', hour=18, minute=30)
scheduler.start()
logging.info("Scheduler started for 6:30 PM daily (Asia/Colombo).")

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Prayer Times Bot is live!"

# === Self-ping thread to prevent shutdown ===
def keep_alive():
    while True:
        time.sleep(600)  # Sleep for 10 minutes
        if not SELF_URL:
            continue
        try:
            requests.get(SELF_URL, timeout=10)
            logging.info("Self-ping successful.")
        except Exception as e:
            logging.error(f"Self-ping failed: {e}")

threading.Thread(target=keep_alive, daemon=True).start()
logging.info("Keep-alive thread started.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
