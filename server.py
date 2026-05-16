print("🔥 PRO PAYMENT BOT LOADED")

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

TRIBUTE_API_KEY = "13b09f95-c752-4280-8491-b080592a"

RENDER_URL = "https://bot-lp4u.onrender.com"

stripe.api_key = STRIPE_SECRET

# ================= PLANS =================

PRICE_MAP = {
        "1m": ("price_1TX1WI5AySZk9F3jAfOTEg6B", 30),
    "3m": ("price_1TX1X05AySZk9F3jwnCsSXrW", 90),
    "6m": ("price_1TX1XJ5AySZk9F3j0kSslAcp", 180),
    "12m": ("price_1TX1XY5AySZk9F3jsjrr9BS6", 365)
}

# ================= DB =================

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
    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        user_id INTEGER,
        method TEXT,
        created_at INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= TELEGRAM =================

def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    requests.post(url, json=payload, timeout=10)

# ================= INVITE =================

def create_invite():
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
        json={"chat_id": CHANNEL_ID, "member_limit": 1},
        timeout=10
    )
    data = r.json()
    return data["result"]["invite_link"] if data.get("ok") else None

# ================= ACCESS SYSTEM =================

def grant_access(user_id, days, method, payment_id):
    conn = sqlite3.connect("subs.db")
    c = conn.cursor()

    # 🔐 ANTI FRAUD 1: duplicate payment
    c.execute("SELECT 1 FROM payments WHERE payment_id=?", (payment_id,))
    if c.fetchone():
        conn.close()
        return

    expire = datetime.utcnow() + timedelta(days=days)

    c.execute("INSERT OR REPLACE INTO subs VALUES (?,?)",
              (user_id, expire.isoformat()))

    c.execute("INSERT INTO payments VALUES (?,?,?,?)",
              (payment_id, user_id, method, int(time.time())))

    conn.commit()
    conn.close()

    link = create_invite()
    if link:
        send(user_id, f"✅ Оплата подтверждена ({method})\n\n🔗 {link}")

# ================= START =================

@app.route("/telegram", methods=["POST"])
def telegram():
    update = request.get_json()
    if not update:
        return "ok"

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]

        if update["message"].get("text") == "/start":
            send(chat_id, "Выбери тариф:", {
                "inline_keyboard": [
                    [{"text": "1m", "callback_data": "1m"}],
                    [{"text": "3m", "callback_data": "3m"}],
                    [{"text": "6m", "callback_data": "6m"}],
                    [{"text": "12m", "callback_data": "12m"}],
                    [{"text": "💳 Tribute", "callback_data": "tribute"}]
                ]
            })
        return "ok"

    if "callback_query" in update:
        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        data = cb["data"]

        # ================= TRIBUTE =================
        if data == "tribute":
            send(user_id, "Открыть оплату:", {
                "inline_keyboard": [[
                    {
                        "text": "Pay Tribute",
                        "url": "https://t.me/tribute/app?startapp=sViL"
                    }
                ]]
            })
            return "ok"

        # ================= STRIPE =================
        if data in PRICE_MAP:
            price_id, days = PRICE_MAP[data]

            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                success_url="https://t.me/",
                metadata={
                    "telegram_id": str(user_id),
                    "days": str(days)
                }
            )

            send(user_id, "Оплата:", {
                "inline_keyboard": [[
                    {"text": "Stripe", "url": session.url},
                    {"text": "Tribute", "url": "https://t.me/tribute/app?startapp=sViL"}
                ]]
            })

    return "ok"

# ================= STRIPE WEBHOOK =================

@app.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except:
        return "bad", 400

    if event["type"] != "checkout.session.completed":
        return "ok"

    s = event["data"]["object"]

    user_id = int(s["metadata"]["telegram_id"])
    days = int(s["metadata"]["days"])
    payment_id = s["id"]

    grant_access(user_id, days, "stripe", payment_id)

    return "ok"

# ================= TRIBUTE WEBHOOK =================
# ⚠️ работает ТОЛЬКО если Tribute реально шлёт webhook

@app.route("/tribute/webhook", methods=["POST"])
def tribute_webhook():
    print("🔥 WEBHOOK ПРИШЁЛ")

    print("HEADERS:", dict(request.headers))
    print("RAW:", request.data)
    print("JSON:", request.get_json())

    return "ok"
# ================= AUTO KICK =================

def checker():
    while True:
        try:
            conn = sqlite3.connect("subs.db")
            c = conn.cursor()

            c.execute("SELECT user_id, expire FROM subs")
            rows = c.fetchall()

            now = datetime.utcnow()

            for user_id, exp in rows:
                if now > datetime.fromisoformat(exp):

                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
                        json={"chat_id": CHANNEL_ID, "user_id": user_id}
                    )

                    c.execute("DELETE FROM subs WHERE user_id=?", (user_id,))
                    conn.commit()

            conn.close()

        except Exception as e:
            print("CHECK ERROR:", e)

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
