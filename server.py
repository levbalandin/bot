print("🔥 NEW VERSION LOADED")

from flask import Flask, request
import requests
import stripe
import threading
import time
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================

BOT_TOKEN = "8685106379:AAET5pcVkmw9uuceDCMllFX_hwRgOguTsTI"
CHANNEL_ID = -1003830259549

STRIPE_SECRET = "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"
STRIPE_WEBHOOK_SECRET = "whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT"

RENDER_URL = "https://bot-lp4u.onrender.com"

stripe.api_key = STRIPE_SECRET

# ================= PLANS =================

PRICE_MAP = {
    "1m": ("price_1TX1WI5AySZk9F3jAfOTEg6B", 30),
    "3m": ("price_1TX1X05AySZk9F3jwnCsSXrW", 90),
    "6m": ("price_1TX1XJ5AySZk9F3j0kSslAcp", 180),
    "12m": ("price_1TX1XY5AySZk9F3jsjrr9BS6", 365)
}

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("subs.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS subs (
        user_id INTEGER PRIMARY KEY,
        expire TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= TELEGRAM =================

def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print("SEND ERROR:", e)

# ================= WEBHOOK =================

@app.route("/telegram", methods=["POST"])
def telegram():

    update = request.get_json()
    if not update:
        return "ok"

    # START
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "1 месяц", "callback_data": "1m"}],
                    [{"text": "3 месяца", "callback_data": "3m"}],
                    [{"text": "6 месяцев", "callback_data": "6m"}],
                    [{"text": "12 месяцев", "callback_data": "12m"}]
                ]
            }
            send(chat_id, "Выбери тариф:", keyboard)

    # CALLBACK
    elif "callback_query" in update:

        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        data = cb["data"]

        if data not in PRICE_MAP:
            send(user_id, "Ошибка тарифа")
            return "ok"

        price_id, days = PRICE_MAP[data]

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1
            }],
            success_url="https://t.me/",
            metadata={
                "telegram_id": str(user_id),
                "days": str(days)
            }
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "💳 ОПЛАТИТЬ", "url": session.url}
            ]]
        }

        send(user_id, "Оплати подписку:", keyboard)

    return "ok"

# ================= STRIPE =================

@app.route("/stripe", methods=["POST"])
def stripe_webhook():

    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "error", 400

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        telegram_id = int(session["metadata"]["telegram_id"])
        days = int(session["metadata"]["days"])

        expire = datetime.utcnow() + timedelta(days=days)

        # сохраняем подписку в базу
        conn = sqlite3.connect("subs.db")
        c = conn.cursor()
        c.execute("""
        INSERT OR REPLACE INTO subs (user_id, expire)
        VALUES (?, ?)
        """, (telegram_id, expire.isoformat()))
        conn.commit()
        conn.close()

        print("ACCESS GRANTED:", telegram_id)

        # ================= ОДНОРАЗОВАЯ ССЫЛКА =================
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
                json={
                    "chat_id": CHANNEL_ID,
                    "member_limit": 1
                },
                timeout=10
            )

            data = r.json()

            if data.get("ok"):
                link = data["result"]["invite_link"]

                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": telegram_id,
                        "text": f"✅ Оплата прошла!\n\nВот твой одноразовый доступ:\n{link}"
                    }
                )
            else:
                print("TELEGRAM ERROR:", data)

        except Exception as e:
            print("INVITE ERROR:", e)

    return "ok"

# ================= AUTO REMOVE =================

def checker():

    while True:
        try:
            conn = sqlite3.connect("subs.db")
            c = conn.cursor()
            c.execute("SELECT user_id, expire FROM subs")
            rows = c.fetchall()
            conn.close()

            now = datetime.utcnow()

            for user_id, expire in rows:
                exp = datetime.fromisoformat(expire)

                if now > exp:
                    print("REMOVING:", user_id)

                    # IMPORTANT FIX: correct Telegram param is user_id
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
                        json={
                            "chat_id": CHANNEL_ID,
                            "user_id": user_id
                        }
                    )

                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/unbanChatMember",
                        json={
                            "chat_id": CHANNEL_ID,
                            "user_id": user_id,
                            "only_if_banned": True
                        }
                    )

                    conn = sqlite3.connect("subs.db")
                    c = conn.cursor()
                    c.execute("DELETE FROM subs WHERE user_id=?", (user_id,))
                    conn.commit()
                    conn.close()

        except Exception as e:
            print("CHECKER ERROR:", e)

        time.sleep(60)

# ================= RUN =================

@app.route("/")
def home():
    return "BOT WORKING"

@app.route("/health")
def health():
    return "OK"

@app.route("/setwebhook")
def set_webhook():
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": f"{RENDER_URL}/telegram"}
    )
    return r.text

if __name__ == "__main__":
    threading.Thread(target=checker, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
