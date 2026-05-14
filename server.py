```python
from flask import Flask, request
import requests
import stripe
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# ---------------- CONFIG ----------------
BOT_TOKEN = "8685106379:AAGU7S34VYnVw9Z1pPMwoX6Xco7YiFSvRRI"
CHANNEL_ID = "-1003830259549"

STRIPE_SECRET = "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"
STRIPE_WEBHOOK_SECRET = "whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT"

stripe.api_key = STRIPE_SECRET

# ---------------- PRICE IDS ----------------
PRICE_MAP = {
    "1m": "price_1TX1WI5AySZk9F3jAfOTEg6B",
    "3m": "price_1TX1X05AySZk9F3jwnCsSXrW",
    "6m": "price_1TX1XJ5AySZk9F3j0kSslAcp",
    "12m": "price_1TX1XY5AySZk9F3jsjrr9BS6"
}

user_subscriptions = {}

# ---------------- TELEGRAM SEND ----------------
def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    response = requests.post(url, json=payload)

    print("TELEGRAM RESPONSE:", response.text)


# ---------------- /START ----------------
def handle_start(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 1 месяц", "callback_data": "1m"}],
            [{"text": "💳 3 месяца", "callback_data": "3m"}],
            [{"text": "💳 6 месяцев", "callback_data": "6m"}],
            [{"text": "💳 12 месяцев", "callback_data": "12m"}]
        ]
    }

    send_message(chat_id, "Выбери тариф:", keyboard)


# ---------------- CALLBACK ----------------
def handle_callback(callback):
    try:
        data = callback["data"]
        user_id = callback["from"]["id"]

        print("CALLBACK:", data)

        if data not in PRICE_MAP:
            send_message(user_id, "Ошибка: тариф не найден")
            return

        price_id = PRICE_MAP[data]

        print("PRICE ID:", price_id)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",

            line_items=[
                {
                    "price": price_id,
                    "quantity": 1
                }
            ],

            success_url="https://t.me/",
            cancel_url="https://t.me/",

            metadata={
                "telegram_id": str(user_id),
                "price_id": price_id
            }
        )

        print("SESSION CREATED")
        print("SESSION URL:", session.url)

        if not session.url:
            send_message(user_id, "Stripe не вернул ссылку")
            return

        keyboard = {
            "inline_keyboard": [[
                {
                    "text": "💳 ОПЛАТИТЬ",
                    "url": session.url
                }
            ]]
        }

        send_message(
            user_id,
            "Оплати по ссылке:",
            keyboard
        )

    except Exception as e:
        print("STRIPE ERROR:", str(e))

        send_message(
            user_id,
            f"Ошибка Stripe:\n{str(e)}"
        )


# ---------------- STRIPE WEBHOOK ----------------
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
        return "error", 400

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        meta = session.get("metadata", {})

        user_id = meta.get("telegram_id")
        price_id = meta.get("price_id")

        print("PAYMENT SUCCESS:", user_id, price_id)

        if user_id and price_id:

            days = {
                PRICE_MAP["1m"]: 30,
                PRICE_MAP["3m"]: 90,
                PRICE_MAP["6m"]: 180,
                PRICE_MAP["12m"]: 365
            }.get(price_id, 0)

            if days:

                user_subscriptions[int(user_id)] = (
                    datetime.now() + timedelta(days=days)
                )

                print("ACCESS GRANTED:", user_id)

                send_message(
                    int(user_id),
                    f"✅ Оплата прошла.\nПодписка активна на {days} дней."
                )

    return "ok", 200


# ---------------- TELEGRAM WEBHOOK ----------------
@app.route("/telegram", methods=["POST"])
def telegram_webhook():

    try:
        update = request.get_json()

        print("UPDATE:", update)

        if "message" in update:

            chat_id = update["message"]["chat"]["id"]

            text = update["message"].get("text", "")

            if text == "/start":
                handle_start(chat_id)

        if "callback_query" in update:

            handle_callback(update["callback_query"])

        return "ok", 200

    except Exception as e:
        print("TELEGRAM ERROR:", e)
        return "error", 200


# ---------------- CHECK ACCESS ----------------
def check_expired():

    import time

    while True:

        now = datetime.now()

        for user_id, expire in list(user_subscriptions.items()):

            if now > expire:

                try:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember"

                    requests.post(url, json={
                        "chat_id": CHANNEL_ID,
                        "user_id": user_id
                    })

                    del user_subscriptions[user_id]

                    print("REMOVED:", user_id)

                except Exception as e:
                    print("REMOVE ERROR:", e)

        time.sleep(60)


# ---------------- HOME ----------------
@app.route("/")
def home():
    return "server running"


# ---------------- START ----------------
if __name__ == "__main__":

    import threading

    threading.Thread(
        target=check_expired,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
```

