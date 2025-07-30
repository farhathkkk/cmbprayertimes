# main.py

import os
import fitz  # PyMuPDF
import datetime
import requests
from telegram import Bot
import time
from flask import Flask
import threading

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GITHUB_PDF_URL = 'https://github.com/farhathkkk/acju-prayer-times/raw/main/Prayer-Times-{month}-2025-COLOMBO.pdf'
LOCAL_PDF = 'today.pdf'

bot = Bot(token=BOT_TOKEN)

def download_pdf(tomorrow):
    month = tomorrow.strftime('%B')  # e.g., July
    url = GITHUB_PDF_URL.format(month=month)
    response = requests.get(url)
    with open(LOCAL_PDF, 'wb') as f:
        f.write(response.content)

def extract_tomorrows_prayers():
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    doc = fitz.open(LOCAL_PDF)
    tomorrow_str = tomorrow.strftime('%-d-%b')  # e.g., '31-Jul'

    for page in doc:
        lines = page.get_text().split('\n')
        for i, line in enumerate(lines):
            if line.strip() == tomorrow_str and i + 7 < len(lines):
                full_line = (
                    lines[i] + " " +
                    lines[i + 1] + " " +
                    lines[i + 2] + " " +
                    lines[i + 3] + " " +
                    lines[i + 4] + " " +
                    lines[i + 5] + " " +
                    lines[i + 6]
                )
                print("Matched line:", full_line)
                return full_line, tomorrow
    return None, tomorrow

def send_daily_prayers():
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    download_pdf(tomorrow)
    raw, t_date = extract_tomorrows_prayers()
    if not raw:
        print("No prayer time found.")
        return

    parts = raw.split()
    if len(parts) < 13:
        print("Line format error.")
        return

    date_str = t_date.strftime("%d %B %Y")
    msg = (
        f"Prayer Times - Colombo (Sri Lanka)\n"
        f"{date_str}\n\n"
        f"Fajr - {parts[1]} {parts[2]}\n"
        f"Sunrise - {parts[3]} {parts[4]}\n"
        f"Luhar - {parts[5]} {parts[6]}\n"
        f"Asar - {parts[7]} {parts[8]}\n"
        f"Maghrib - {parts[9]} {parts[10]}\n"
        f"Isha - {parts[11]} {parts[12]}\n\n"
        f"{{ACJU}}"
    )

    bot.send_message(chat_id=CHAT_ID, text=msg)

# === DAILY SCHEDULER ===
def scheduler_loop():
    while True:
        now = datetime.datetime.now()
        if now.hour == 19 and now.minute == 25:
            send_daily_prayers()
            time.sleep(60)
        time.sleep(20)

# Start scheduler in a background thread
threading.Thread(target=scheduler_loop).start()

# === KEEP RENDER OR REPLIT ALIVE ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

if __name__ == '__main__':
    send_daily_prayers()  # Send immediately on startup
    app.run(host='0.0.0.0', port=8080)
