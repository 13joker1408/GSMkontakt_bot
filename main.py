import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram.ext import ApplicationBuilder

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 216903753))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecretpath")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")

MODEL, CONDITION, KIT, DISTRICT = range(4)

main_menu_keyboard = [
    [KeyboardButton("📱 Оставить заявку")],
    [KeyboardButton("ℹ️ О нас")],
    [KeyboardButton("🏬 Адреса и контакты")]
]
main_menu = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

app = FastAPI()
telegram_app: Application = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие:", reply_markup=main_menu)

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши модель твоей техники:")
    return MODEL

async def model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Укажи состояние техники:")
    return CONDITION

async def condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['condition'] = update.message.text
    await update.message.reply_text("Что входит в комплект?")
    return KIT

async def kit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['kit'] = update.message.text
    await update.message.reply_text("Укажи район:")
    return DISTRICT

async def district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    summary = (
        f"📦 Новая заявка:\n\n"
        f"🔹 Модель: {context.user_data['model']}\n"
        f"🔹 Состояние: {context.user_data['condition']}\n"
        f"🔹 Комплект: {context.user_data['kit']}\n"
        f"🔹 Район: {context.user_data['district']}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)
    await update.message.reply_text("Спасибо! Мы скоро свяжемся с тобой.", reply_markup=main_menu)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Заявка отменена.", reply_markup=main_menu)
    return ConversationHandler.END

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Мы — скупка цифровой техники с 2013 года.\n"
        "Принимаем смартфоны, ноутбуки, планшеты. Оценка за 5 минут!\n"
        "Принимаем только полностью рабочую технику"
    )

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏬 Наши адреса:\n"
        "1. 📍 Пролетарский: ул. Ложевая, д.125а, ТЦ «ПРОЛЕТАРСКИЙ»\n"
        "2. 📍 Заречье: ул. Максима Горького, д.35а\n"
        "3. 📍 Центр: ул. Каминского, д.4Б\n"
        "4. 📍 Привокзальный: Красноармейский пр-т, д.19, ТЦ «ФАБРИКАНТ»\n"
        "5. 📍 Привокзальный: ул. 9-мая д.2, «SPAR»\n"
        "📞 Телефон: 8-800-302-20-71\n"
        "🌐 Сайт: gsmkontakt.ru\n"
        "Telegram: @Strjke"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Как работает бот:\n\n"
        "Нажми кнопку '📱 Оставить заявку', чтобы отправить информацию о технике, которую хочешь продать.\n"
        "Также ты можешь узнать адреса магазинов и контакты, используя соответствующие кнопки."
    )

@app.post(f"/{WEBHOOK_SECRET}")
async def telegram_webhook(req: Request):
    body = await req.json()
    update = Update.de_json(body, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    global telegram_app

    telegram_app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^📱 Оставить заявку$"), start_form)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition)],
            KIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, kit)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, district)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    telegram_app.add_handler(conv_handler)
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ℹ️ О нас$"), about))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏬 Адреса и контакты$"), contacts))

    await telegram_app.initialize()
    await telegram_app.start()
    
    webhook_url = f"{APP_URL}/{WEBHOOK_SECRET}"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
