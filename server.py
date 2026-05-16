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

    c.execute("""
    CREATE TABLE IF NOT EXISTS tribute_payments (
        payment_id TEXT PRIMARY KEY,
        user_id INTEGER,
        plan TEXT,
        status TEXT,
        created_at INTEGER
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

    requests.post(url, json=data, timeout=10)

# ================= WEBHOOK =================

@app.route("/telegram", methods=["POST"])
def telegram():

    update = request.get_json()
    if not update:
        return "ok"

    # ================= START =================
    if "message" in update:

        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "1 месяц", "callback_data": "1m"}],
                    [{"text": "3 месяца", "callback_data": "3m"}],
                    [{"text": "6 месяцев", "callback_data": "6m"}],
                    [{"text": "12 месяцев", "callback_data": "12m"}],
                    [{"text": "💳 Tribute", "callback_data": "tribute"}]
                ]
            }

            send(chat_id, "Выбери тариф:", keyboard)

        return "ok"

    # ================= CALLBACK =================
    if "callback_query" in update:

        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        data = cb["data"]

        # ================= TRIBUTE =================
        if data == "tribute":

            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 Оплатить через Tribute", "url": f"https://tribute-pay.com/pay?user_id={user_id}"}]
                ]
            }

            send(user_id, "Оплата Tribute:", keyboard)
            return "ok"

        # ================= STRIPE =================
        if data in PRICE_MAP:

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
                    {"text": "💳 ОПЛАТИТЬ STRIPE", "url": session.url},
                    {"text": "⚡ TRIBUTE", "url": f"https://tribute-pay.com/pay?user_id={user_id}&plan={data}"}
                ]]
            }

            send(user_id, "Выбери способ оплаты:", keyboard)
            return "ok"

    return "ok"

# ================= STRIPE WEBHOOK =================

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
        print("STRIPE WEBHOOK ERROR:", e)
        return "bad signature", 400

    if event["type"] != "checkout.session.completed":
        return "ok"

    session = event["data"]["object"]

    try:
        telegram_id = int(session["metadata"]["telegram_id"])
        days = int(session["metadata"]["days"])

        expire = datetime.utcnow() + timedelta(days=days)

        conn = sqlite3.connect("subs.db")
        c = conn.cursor()

        c.execute("""
            INSERT OR REPLACE INTO subs (user_id, expire)
            VALUES (?, ?)
        """, (telegram_id, expire.isoformat()))

        conn.commit()
        conn.close()

        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
            json={
                "chat_id": CHANNEL_ID,
                "member_limit": 1
            },
            timeout=10
        )

        res = r.json()

        if res.get("ok"):
            link = res["result"]["invite_link"]

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": f"✅ Stripe оплата прошла!\n\n{link}"
                }
            )

    except Exception as e:
        print("STRIPE PROCESS ERROR:", e)

    return "ok"

# ================= TRIBUTE WEBHOOK =================

@app.route("/tribute/webhook", methods=["POST"])
def tribute_webhook():
    try:
        data = request.get_json()
        if not data:
            return "ok"

        user_id = int(data.get("user_id", 0))
        plan = data.get("plan")
        status = data.get("status")
        payment_id = data.get("payment_id")

        if not user_id or not plan or not payment_id:
            return "bad request"

        if status != "success":
            return "ok"

        # ================= ANTI FRAUD =================
        conn = sqlite3.connect("subs.db")
        c = conn.cursor()

        c.execute("SELECT payment_id FROM tribute_payments WHERE payment_id=?", (payment_id,))
        if c.fetchone():
            conn.close()
            return "duplicate"

        if plan not in PRICE_MAP:
            conn.close()
            return "invalid plan"

        days = PRICE_MAP[plan][1]

        expire = datetime.utcnow() + timedelta(days=days)

        # save subscription
        c.execute("""
            INSERT OR REPLACE INTO subs (user_id, expire)
            VALUES (?, ?)
        """, (user_id, expire.isoformat()))

        # save payment log
        c.execute("""
            INSERT INTO tribute_payments (payment_id, user_id, plan, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (payment_id, user_id, plan, "paid", int(time.time())))

        conn.commit()
        conn.close()

        # ================= INVITE LINK =================
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
            json={
                "chat_id": CHANNEL_ID,
                "member_limit": 1
            },
            timeout=10
        )

        res = r.json()

        if res.get("ok"):
            link = res["result"]["invite_link"]

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": f"⚡ Tribute оплата прошла!\n\nВот доступ:\n{link}"
                }
            )

        return "ok"

    except Exception as e:
        print("TRIBUTE ERROR:", e)
        return "error"

# ================= CHECKER =================

def checker():
    while True:
        try:
            conn = sqlite3.connect("subs.db")
            c = conn.cursor()

            c.execute("SELECT user_id, expire FROM subs")
            rows = c.fetchall()

            now = datetime.utcnow()

            for user_id, expire in rows:
                try:
                    if now > datetime.fromisoformat(expire):

                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
                            json={
                                "chat_id": CHANNEL_ID,
                                "user_id": user_id
                            },
                            timeout=10
                        )

                        c.execute("DELETE FROM subs WHERE user_id=?", (user_id,))
                        conn.commit()

                except Exception as inner:
                    print("CHECKER USER ERROR:", inner)

            conn.close()

        except Exception as e:
            print("CHECKER ERROR:", e)

        time.sleep(60)

# ================= RUN =================

@app.route("/")
def home():
    return "OK"

@app.route("/setwebhook")
def set_webhook():
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": f"{RENDER_URL}/telegram"}
    )
    return "ok"

if __name__ == "__main__":
    threading.Thread(target=checker, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
