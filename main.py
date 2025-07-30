import os
import fitz  # PyMuPDF
import datetime
import requests
from telegram import Bot
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# Load from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # '@cmbprayertimes' or numeric ID

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# GitHub URL
GITHUB_PDF_URL = 'https://github.com/farhathkkk/acju-prayer-times/raw/main/Prayer-Times-{month}-2025-COLOMBO.pdf'
LOCAL_PDF = 'today.pdf'

def download_pdf():
    month = datetime.datetime.now().strftime('%B')
    url = GITHUB_PDF_URL.format(month=month)
    response = requests.get(url)
    with open(LOCAL_PDF, 'wb') as f:
        f.write(response.content)

def extract_tomorrow_prayers():
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    day = tomorrow.day
    doc = fitz.open(LOCAL_PDF)
    for page in doc:
        lines = page.get_text().split('\n')
        for line in lines:
            if line.startswith(f"{day}-Jul") or line.startswith(f"{day} "):
                return line
    return None

def send_daily_prayers():
    try:
        download_pdf()
        raw = extract_tomorrow_prayers()
        if not raw:
            print("No prayer time found.")
            return
        parts = raw.split()
        if len(parts) < 7:
            print("Line format error.")
            return

        date_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%d %B %Y")
        msg = (
            f"🕌 *Prayer Times - Colombo (Sri Lanka)*\n"
            f"📅 {date_str}\n\n"
            f"Fajr: {parts[1]}\n"
            f"Sunrise: {parts[2]}\n"
            f"Luhar: {parts[3]}\n"
            f"Asar: {parts[4]}\n"
            f"Maghrib: {parts[5]}\n"
            f"Isha: {parts[6]}\n\n"
            f"_ACJU_"
        )
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        print("✅ Sent prayer times.")
    except Exception as e:
        print("❌ Failed to send prayer times:", e)

# Flask route to keep Render alive
@app.route('/')
def home():
    return "Bot is running on Render!"

# Schedule the daily task
scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_prayers, trigger='cron', hour=18, minute=30)  # 6 PM server time
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
