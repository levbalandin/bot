from flask import Flask, request
import stripe
import threading
import time
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

app = Flask(__name__)

# ---------------- TELEGRAM ----------------
BOT_TOKEN = "8685106379:AAGU7S34VYnVw9Z1pPMwoX6Xco7YiFSvRRI"
CHANNEL_ID = -1003830259549

# ---------------- STRIPE (LIVE MODE) ----------------
STRIPE_SECRET = "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"
STRIPE_WEBHOOK_SECRET = "whsec_PMuwx30H9kdvfYaeEz258fFBzlt89GIT"

stripe.api_key = STRIPE_SECRET

# ---------------- ТАРИФЫ ----------------
PRICE_MAP = {
    "1m": "price_1TX1WI5AySZk9F3jAfOTEg6B",
    "3m": "price_1TX1X05AySZk9F3jwnCsSXrW",
    "6m": "price_1TX1XJ5AySZk9F3j0kSslAcp",
    "12m": "price_1TX1XY5AySZk9F3jsjrr9BS6"
}

# ---------------- ДОБАВЛЕНО: ХРАНЕНИЕ ПОДПИСОК ----------------
user_subscriptions = {}
bot_app = None


# ---------------- START КНОПКИ ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 1 месяц — 20€", callback_data="1m")],
        [InlineKeyboardButton("💳 3 месяца — 51€", callback_data="3m")],
        [InlineKeyboardButton("💳 6 месяцев — 95€", callback_data="6m")],
        [InlineKeyboardButton("💳 12 месяцев — 169€", callback_data="12m")]
    ]

    await update.message.reply_text(
        "Выбери тариф:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- CALLBACK ----------------
async def choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        plan = query.data
        price_id = PRICE_MAP[plan]

        user_id = query.from_user.id

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
                "price_id": price_id
            }
        )

        keyboard = [
            [InlineKeyboardButton("💳 ОПЛАТИТЬ", url=session.url)]
        ]

        await query.message.reply_text(
            "Нажми для оплаты:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        print("BUTTON ERROR:", e)


# ---------------- ДОБАВЛЕНО: ВЫДАЧА ДОСТУПА ----------------
def send_access(telegram_id, days):
    expire = datetime.now() + timedelta(days=days)
    user_subscriptions[telegram_id] = expire
    print(f"ACCESS SENT: {telegram_id} до {expire}")


# ---------------- WEBHOOK STRIPE ----------------
@app.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook error:", e)
        return "error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        metadata = session.get("metadata", {})
        telegram_id = metadata.get("telegram_id")
        price_id = metadata.get("price_id")

        if telegram_id and price_id:
            if price_id == PRICE_MAP["1m"]:
                days = 30
            elif price_id == PRICE_MAP["3m"]:
                days = 90
            elif price_id == PRICE_MAP["6m"]:
                days = 180
            elif price_id == PRICE_MAP["12m"]:
                days = 365
            else:
                days = 0

            if days:
                send_access(int(telegram_id), days)

    return "ok", 200


# ---------------- ДОБАВЛЕНО: АВТО-ВЫКИДЫВАНИЕ ----------------
def
