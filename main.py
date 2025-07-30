# main.py
import fitz  # PyMuPDF
import datetime
import requests
from telegram import Bot
import threading
import time
from flask import Flask

BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = '@your_channel_username'  # or numeric ID for a user/chat
GITHUB_PDF_URL = 'https://github.com/farhathkkk/acju-prayer-times/raw/main/Prayer-Times-{month}-2025-COLOMBO.pdf'
LOCAL_PDF = 'today.pdf'

bot = Bot(token=BOT_TOKEN)

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
                print("Matched line:", line)
                return line
    return None

def send_daily_prayers():
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
        f"Prayer Times - Colombo (Sri Lanka)\n"
        f"{date_str}\n\n"
        f"Fajr - {parts[1]}\n"
        f"Sunrise - {parts[2]}\n"
        f"Luhar - {parts[3]}\n"
        f"Asar - {parts[4]}\n"
        f"Maghrib - {parts[5]}\n"
        f"Isha - {parts[6]}\n\n"
        f"{{ACJU}}"
    )
    bot.send_message(chat_id=CHAT_ID, text=msg)

# Scheduler to run at 8:00 PM daily
def scheduler_loop():
    while True:
        now = datetime.datetime.now()
        if now.hour == 18 and now.minute == 0:
            send_daily_prayers()
            time.sleep(60)
        time.sleep(20)

# Flask app to keep server alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running on Render!"

# Start server and scheduler
threading.Thread(target=scheduler_loop).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
