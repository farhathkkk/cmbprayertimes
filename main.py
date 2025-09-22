import os
import fitz  # PyMuPDF
import datetime
import requests
from telegram import Bot
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
import time

# --- Basic logging setup ---
# This is better than print() for tracking issues on a server.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === CONFIGURATION ===
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    CHAT_ID = os.environ["CHAT_ID"]
    # A secret key to protect the manual trigger endpoint
    TEST_TRIGGER_KEY = os.environ.get("TEST_TRIGGER_KEY", "default-secret-key")
except KeyError as e:
    logging.critical(f"FATAL: Environment variable {e} not set. The application cannot start.")
    exit() # Exit if critical config is missing

GITHUB_PDF_URL_TEMPLATE = 'https://github.com/farhathkkk/acju-prayer-times/raw/main/Prayer-Times-{month}-{year}-COLOMBO.pdf'
LOCAL_PDF_FILENAME = 'prayer_times.pdf'

# Initialize the Telegram Bot
bot = Bot(token=BOT_TOKEN)

# === CORE LOGIC ===

def download_pdf_if_needed(target_date):
    """
    Downloads the PDF for the target month only if it doesn't already exist
    or if the month has changed. This prevents needless daily downloads.
    """
    month = target_date.strftime('%B')
    year = target_date.strftime('%Y')
    
    if os.path.exists(LOCAL_PDF_FILENAME):
        file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(LOCAL_PDF_FILENAME))
        if file_mod_time.strftime('%B') == month:
            logging.info(f"PDF for {month} already exists. Skipping download.")
            return True

    logging.info(f"Downloading prayer times PDF for {month} {year}...")
    url = GITHUB_PDF_URL_TEMPLATE.format(month=month, year=year)

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(LOCAL_PDF_FILENAME, 'wb') as f:
            f.write(response.content)
        logging.info("PDF downloaded successfully.")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download PDF from {url}. Error: {e}")
        return False

def extract_tomorrows_prayers(tomorrow_date):
    """Extracts prayer times for a specific date from the local PDF."""
    try:
        doc = fitz.open(LOCAL_PDF_FILENAME)
    except fitz.errors.FitzError as e:
        logging.error(f"Could not open or read the PDF file '{LOCAL_PDF_FILENAME}'. It may be corrupted. Error: {e}")
        return None

    tomorrow_str = tomorrow_date.strftime('%#d-%b' if os.name == 'nt' else '%-d-%b') # Format for date, e.g., '23-Sep'

    for page in doc:
        text = page.get_text("text")
        lines = text.split('\n')
        for line in lines:
            # **THE FIX**: Check if the line *starts with* the date string.
            # This handles cases where date and times are on the same line.
            if line.strip().startswith(tomorrow_str):
                logging.info(f"Found matching line for '{tomorrow_str}': {line.strip()}")
                return line.strip()
    
    logging.warning(f"Could not find prayer times for date string '{tomorrow_str}' in the PDF.")
    return None

def send_daily_prayers():
    """
    The main job executed by the scheduler. It handles the entire process
    of downloading, parsing, and sending the prayer times.
    """
    try:
        logging.info("Scheduler triggered. Running send_daily_prayers job...")
        
        colombo_tz = pytz.timezone("Asia/Colombo")
        tomorrow = datetime.datetime.now(colombo_tz) + datetime.timedelta(days=1)

        if not download_pdf_if_needed(tomorrow):
            bot.send_message(chat_id=CHAT_ID, text="Alert: Could not download the prayer times PDF. The file might be missing from the GitHub repository.")
            return

        raw_line = extract_tomorrows_prayers(tomorrow)
        if not raw_line:
            date_to_find = tomorrow.strftime('%#d-%b' if os.name == 'nt' else '%-d-%b')
            bot.send_message(chat_id=CHAT_ID, text=f"🔍 **Parsing Error** 🔍\n\nCould not find the prayer times for tomorrow ({date_to_find}) in the PDF. Please check the PDF's date format.")
            return

        parts = raw_line.split()
        # **THE FIX**: Based on the PDF image, we expect 13 parts.
        # e.g., '23-Sep', '4:43', 'AM', '6:00', 'AM', ...
        if len(parts) < 13:
            logging.error(f"Line format error. Expected at least 13 parts, but got {len(parts)}: '{raw_line}'")
            bot.send_message(chat_id=CHAT_ID, text=f"📄 **Parsing Error** 📄\n\nFound the line for tomorrow, but the format was incorrect:\n`{raw_line}`")
            return

        date_str = tomorrow.strftime("%A, %d %B %Y")
        
        # **THE FIX**: Re-index the parts to combine time and AM/PM.
        fajr_time = f"{parts[1]} {parts[2]}"
        sunrise_time = f"{parts[3]} {parts[4]}"
        luhar_time = f"{parts[5]} {parts[6]}"
        asar_time = f"{parts[7]} {parts[8]}"
        maghrib_time = f"{parts[9]} {parts[10]}"
        isha_time = f"{parts[11]} {parts[12]}"

        msg = (
            f"🕌 *Prayer Times - Colombo, Sri Lanka*\n"
            f"📅 *{date_str}*\n\n"
            f" Fajr\t\t\t- {fajr_time}\n"
            f" Sunrise\t- {sunrise_time}\n"
            f" Luhar\t\t- {luhar_time}\n"
            f" Asar\t\t\t- {asar_time}\n"
            f" Maghrib\t- {maghrib_time}\n"
            f" Isha\t\t\t- {isha_time}\n\n"
            f"Source: ACJU"
        )

        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        logging.info("Prayer times message sent successfully.")

    except Exception as e:
        logging.critical(f"An unexpected error occurred in the 'send_daily_prayers' job: {e}", exc_info=True)
        try:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 **BOT ERROR** 🚨\n\nThe prayer times job failed with an error:\n`{e}`\n\nPlease check the logs.")
        except Exception as telegram_error:
            logging.error(f"Could not even send the error notification to Telegram: {telegram_error}")

# === SCHEDULER SETUP ===
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Colombo"))
scheduler.add_job(send_daily_prayers, trigger='cron', hour=18, minute=30)
scheduler.start()
logging.info("Scheduler started. Job is scheduled for 6:30 PM (Asia/Colombo) daily.")


# === FLASK WEB SERVER ===
app = Flask(__name__)

@app.route('/')
def home():
    """A simple endpoint to confirm the bot is running."""
    return "Prayer Times Bot is alive and the scheduler is running."

@app.route('/test-prayers')
def test_prayers():
    """A manual trigger for the prayer time job for easy debugging."""
    provided_key = request.args.get('key')
    if provided_key != TEST_TRIGGER_KEY:
        return "Unauthorized", 401
    
    logging.info("Manual trigger received for 'send_daily_prayers'.")
    scheduler.add_job(send_daily_prayers, 'date')
    return "OK, triggered the prayer time job. Check your Telegram and the logs.", 200


# The main entry point for the application.
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

