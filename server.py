from flask import Flask, request
import requests
import stripe

app = Flask(__name__)

# ================= CONFIG =================
BOT_TOKEN = "ВСТАВЬ_СЮДА_НОВЫЙ_ТОКЕН_ИЗ_BOTFATHER"
CHANNEL_ID = "-1003830259549"

STRIPE_SECRET = "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"

stripe.api_key = STRIPE_SECRET

PRICE_MAP = {
    "1m": "price_1TX1WI5AySZk9F3jAfOTEg6B",
    "3m": "price_1TX1X05AySZk9F3jwnCsSXrW",
    "6m": "price_1TX1XJ5AySZk9F3j0kSslAcp",
    "12m": "price_1TX1XY5AySZk9F3jsjrr9BS6"
}

# ================= TELEGRAM =================
def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    r = requests.post(url, json=data)
    print("TG:", r.text)

# ================= START =================
def start(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "1 месяц", "callback_data": "1m"}],
            [{"text": "3 месяца", "callback_data": "3m"}],
            [{"text": "6 месяцев", "callback_data": "6m"}],
            [{"text": "12 месяцев", "callback_data": "12m"}]
        ]
    }

    send(chat_id, "Выбери тариф:", keyboard)

# ================= CALLBACK =================
def callback_handler(cb):
    user_id = cb["from"]["id"]
    data = cb["data"]

    if data not in PRICE_MAP:
        send(user_id, "Ошибка тарифа")
        return

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": PRICE_MAP[data],
                "quantity": 1
            }],
            success_url="https://t.me/",
            cancel_url="https://t.me/",
            metadata={"telegram_id": str(user_id)}
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "💳 ОПЛАТИТЬ", "url": session.url}
            ]]
        }

        send(user_id, "Нажми для оплаты:", keyboard)

    except Exception as e:
        print("STRIPE ERROR:", e)
        send(user_id, "Ошибка оплаты")

# ================= WEBHOOK =================
@app.route("/telegram", methods=["POST"])
def telegram():
    update = request.get_json()

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            start(chat_id)

    elif "callback_query" in update:
        callback_handler(update["callback_query"])

    return "ok"

# ================= HEALTH =================
@app.route("/")
def home():
    return "OK"

# ================= SET WEBHOOK =================
@app.route("/setwebhook")
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.post(url, data={"url": "https://bot-lp4u.onrender.com/telegram"})
    return r.text

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
