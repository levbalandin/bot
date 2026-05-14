from flask import Flask, request
import requests
import stripe
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================
BOT_TOKEN = "8685106379:AAET5pcVkmw9uuceDCMllFX_hwRgOguTsTI"
CHANNEL_ID = -1003830259549

STRIPE_SECRET = "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"
STRIPE_WEBHOOK_SECRET = "whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT"

stripe.api_key = STRIPE_SECRET

# ================= PLANS =================
PRICE_MAP = {
    "1m": ("price_1TX1WI5AySZk9F3jAfOTEg6B", 30),
    "3m": ("price_1TX1X05AySZk9F3jwnCsSXrW", 90),
    "6m": ("price_1TX1XJ5AySZk9F3j0kSslAcp", 180),
    "12m": ("price_1TX1XY5AySZk9F3jsjrr9BS6", 365)
}

# ================= MEMORY =================
user_subscriptions = {}

# ================= TELEGRAM =================
def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    requests.post(url, json=data)

# ================= START =================
@app.route("/telegram", methods=["POST"])
def telegram():
    update = request.get_json()

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

    elif "callback_query" in update:
        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        data = cb["data"]

        if data not in PRICE_MAP:
            send(user_id, "Ошибка тарифа")
            return "ok"

        price_id, days = PRICE_MAP[data]

        try:
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

            send(user_id, "Оплати по кнопке:", keyboard)

        except Exception as e:
            print("STRIPE ERROR:", e)

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

        telegram_id = session["metadata"]["telegram_id"]
        days = int(session["metadata"]["days"])

        expire = datetime.now() + timedelta(days=days)
        user_subscriptions[int(telegram_id)] = expire

        print(f"ACCESS GRANTED {telegram_id} until {expire}")

    return "ok"

# ================= AUTO REMOVE =================
def checker():
    while True:
        now = datetime.now()

        for user_id, expire in list(user_subscriptions.items()):
            if now > expire:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
                        json={
                            "chat_id": CHANNEL_ID,
                            "user_id": user_id
                        }
                    )

                    del user_subscriptions[user_id]
                    print("REMOVED:", user_id)

                except Exception as e:
                    print("REMOVE ERROR:", e)

        time.sleep(60)

# ================= HOME =================
@app.route("/")
def home():
    return "OK"

# ================= START THREAD =================
if __name__ == "__main__":
    threading.Thread(target=checker, daemon=True).start()

    app.run(host="0.0.0.0", port=10000)
