import os
import json
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import schedule
import time

app = Flask(__name__)
CORS(app)

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # <-- שים כאן את הטוקן שלך
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# קובץ לשמירת התזכורות (בסביבת production השתמש ב-DB)
REMINDERS_FILE = "reminders.json"

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def send_telegram_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def check_reminders():
    reminders = load_reminders()
    now = datetime.now()
    updated = []

    for reminder in reminders:
        remind_time = datetime.fromisoformat(reminder["datetime"])
        
        if now >= remind_time and not reminder.get("sent"):
            text = f"🔔 <b>תזכורת!</b>\n\n{reminder['text']}"
            if reminder.get("description"):
                text += f"\n\n📝 {reminder['description']}"
            
            send_telegram_message(reminder["chat_id"], text)
            reminder["sent"] = True
            
            # אם חוזר — תזמן מחדש
            if reminder.get("repeat") and reminder["repeat"] != "once":
                repeat = reminder["repeat"]
                if repeat == "daily":
                    reminder["datetime"] = (remind_time + timedelta(days=1)).isoformat()
                elif repeat == "weekly":
                    reminder["datetime"] = (remind_time + timedelta(weeks=1)).isoformat()
                elif repeat == "monthly":
                    next_month = remind_time.replace(month=remind_time.month % 12 + 1)
                    reminder["datetime"] = next_month.isoformat()
                reminder["sent"] = False
        
        updated.append(reminder)
    
    save_reminders(updated)

@app.route("/add-reminder", methods=["POST"])
def add_reminder():
    data = request.json
    
    required = ["chat_id", "text", "datetime"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    reminder = {
        "chat_id": data["chat_id"],
        "text": data["text"],
        "description": data.get("description", ""),
        "datetime": data["datetime"],
        "repeat": data.get("repeat", "once"),
        "sent": False,
        "created_at": datetime.now().isoformat()
    }

    reminders = load_reminders()
    reminders.append(reminder)
    save_reminders(reminders)

    # שלח הודעת אישור
    confirm_text = f"✅ <b>תזכורת נקבעה!</b>\n\n📌 {reminder['text']}"
    if reminder["description"]:
        confirm_text += f"\n📝 {reminder['description']}"
    confirm_text += f"\n⏰ {reminder['datetime'][:16].replace('T', ' בשעה ')}"
    
    repeat_labels = {"once": "פעם אחת", "daily": "כל יום", "weekly": "כל שבוע", "monthly": "כל חודש"}
    confirm_text += f"\n🔁 {repeat_labels.get(reminder['repeat'], 'פעם אחת')}"
    
    send_telegram_message(data["chat_id"], confirm_text)

    return jsonify({"success": True, "message": "Reminder added!"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

def run_scheduler():
    schedule.every(1).minutes.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    app.run(host="0.0.0.0", port=5000)
