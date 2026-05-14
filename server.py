from flask import Flask, request
import requests
import stripe
import os

app = Flask(__name__)

# ================= ENV (Render Variables) =================

BOT_TOKEN = os.environ.get("8685106379:AAGU7S34VYnVw9Z1pPMwoX6Xco7YiFSvRRI")
CHANNEL_ID = os.environ.get("-1003830259549")

STRIPE_SECRET = os.environ.get("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")
STRIPE_WEBHOOK_SECRET = os.environ.get("whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT")

RENDER_URL = os.environ.get("RENDER_URL")

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

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text
        }

        if keyboard:
            payload["reply_markup"] = keyboard

        requests.post(url, json=payload)

    except Exception as e:
        print("SEND ERROR:", e)


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
                {
                    "text": "💳 ОПЛАТИТЬ",
                    "url": session.url
                }
            ]]
        }

        send_message(user_id, "Нажмите кнопку для оплаты:", keyboard)

    except Exception as e:
        print("STRIPE ERROR:", e)
        send_message(user_id, "Ошибка оплаты, попробуйте позже")


# ================= STRIPE WEBHOOK =================

@app.route("/stripe", methods=["POST"])
def stripe_webhook():

    payload = request.get_data()
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

        try:
            invite = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
                json={
                    "chat_id": CHANNEL_ID,
                    "member_limit": 1
                }
            ).json()

            link = invite["result"]["invite_link"]

            send_message(
                telegram_id,
                f"✅ Оплата прошла!\n\nВот доступ:\n{link}"
            )

        except Exception as e:
            print("INVITE ERROR:", e)
            send_message(telegram_id, "Ошибка выдачи доступа")

    return "ok", 200


# ================= TELEGRAM WEBHOOK =================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():

    update = request.get_json()

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text")

        if text == "/start":
            handle_start(chat_id)

    if "callback_query" in update:
        handle_callback(update["callback_query"])

    return "ok", 200


# ================= HOME =================

@app.route("/")
def home():
    return "Bot running"


# ================= SET WEBHOOK =================

@app.route("/setwebhook")
def set_webhook():

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"

    webhook_url = f"{RENDER_URL}/telegram"

    return requests.post(url, json={"url": webhook_url}).text


# ================= MAIN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
