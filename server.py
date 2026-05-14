from flask import Flask, request
import requests
import stripe
import os

app = Flask(__name__)

# ================= CONFIG =================
BOT_TOKEN = "8685106379:AAGU7S34VYnVw9Z1pPMwoX6Xco7YiFSvRRI"
CHANNEL_ID = "-1003830259549"

STRIPE_SECRET = "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"
STRIPE_WEBHOOK_SECRET = "whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT"

RENDER_URL = "https://bot-lp4u.onrender.com"

stripe.api_key = STRIPE_SECRET


# ================= PRICE IDS =================
PRICE_MAP = {
    "1m": "price_1TX1WI5AySZk9F3jAfOTEg6B",
    "3m": "price_1TX1X05AySZk9F3jwnCsSXrW",
    "6m": "price_1TX1XJ5AySZk9F3j0kSslAcp",
    "12m": "price_1TX1XY5AySZk9F3jsjrr9BS6"
}


# ================= TELEGRAM =================
def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    r = requests.post(url, json=payload)
    print("TG RESPONSE:", r.text)   # <-- важно для дебага


# ================= START =================
def handle_start(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 1 месяц", "callback_data": "1m"}],
            [{"text": "💳 3 месяца", "callback_data": "3m"}],
            [{"text": "💳 6 месяцев", "callback_data": "6m"}],
            [{"text": "💳 12 месяцев", "callback_data": "12m"}]
        ]
    }

    send_message(chat_id, "Выберите тариф:", keyboard)


# ================= CALLBACK =================
def handle_callback(callback):
    user_id = callback["from"]["id"]
    data = callback["data"]

    if data not in PRICE_MAP:
        send_message(user_id, "Ошибка тарифа")
        return

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": PRICE_MAP[data],
                "quantity": 1
            }],
            success_url="https://t.me/",
            cancel_url="https://t.me/",
            metadata={
                "telegram_id": str(user_id)
            }
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "💳 ОПЛАТИТЬ", "url": session.url}
            ]]
        }

        send_message(user_id, "Нажмите кнопку для оплаты:", keyboard)

    except Exception as e:
        print("STRIPE ERROR:", e)
        send_message(user_id, "Stripe ошибка")


# ================= WEBHOOK =================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    update = request.get_json()

    if not update:
        return "ok"

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            handle_start(chat_id)

    elif "callback_query" in update:
        handle_callback(update["callback_query"])

    return "ok"


@app.route("/")
def home():
    return "OK"


# ================= SET WEBHOOK DEBUG =================
@app.route("/setwebhook")
def set_webhook():
    # проверка токена (ВАЖНО)
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
    print("GETME:", r.text)

    # установка webhook
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r2 = requests.post(url, data={"url": f"{RENDER_URL}/telegram"})

    return {
        "getme": r.text,
        "webhook": r2.text
    }


# ================= MAIN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
