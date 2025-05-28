import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler, CallbackQueryHandler
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

MODEL, CONDITION, KIT, DISTRICT, PHONE = range(5)

main_menu_keyboard = [
    [KeyboardButton("ℹ️ О нас")],
    [KeyboardButton("🏬 Адреса и контакты")]
]
main_menu = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

inline_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 Оставить заявку", callback_data="start_form")],
    [InlineKeyboardButton("🌐 Сайт", url="https://gsmkontakt.ru")],
    [InlineKeyboardButton("Позвонить: +7 800 302-20-71", callback_data="show_phone")]
])

app = FastAPI()
telegram_app: Application = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие:", reply_markup=inline_menu)
    await update.message.reply_text("Или используй кнопки ниже для информации:", reply_markup=main_menu)
    
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "show_phone":
        await query.edit_message_text("Позвонить можно по номеру: +7 800 302-20-71")

async def start_form_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Напиши модель твоей техники:")
    return MODEL

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

    contact_button = KeyboardButton("📞 Отправить номер", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text("Нажми кнопку ниже, чтобы отправить свой номер телефона:", reply_markup=keyboard)
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        phone_number = contact.phone_number
        context.user_data['phone'] = phone_number

        username = update.effective_user.username
        full_name = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()

        summary = (
            f"📦 Новая заявка:\n\n"
            f"👤 Имя: {full_name}\n"
            f"🔗 Username: @{username if username else 'не указан'}\n"
            f"📞 Номер телефона: {phone_number}\n\n"
            f"🔹 Модель: {context.user_data['model']}\n"
            f"🔹 Состояние: {context.user_data['condition']}\n"
            f"🔹 Комплект: {context.user_data['kit']}\n"
            f"🔹 Район: {context.user_data['district']}"
        )

        await context.bot.send_message(chat_id=ADMIN_ID, text=summary)
        await update.message.reply_text("Спасибо! Мы скоро свяжемся с тобой.", reply_markup=main_menu)
        return ConversationHandler.END
    else:
        contact_button = KeyboardButton("📞 Отправить номер", request_contact=True)
        keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Пожалуйста, нажми кнопку ниже, чтобы мы могли с тобой связаться:", reply_markup=keyboard)
        return PHONE

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
        "1. 📍 Пролетарский: ул. Ложевая, д.125а, ТЦ «ПРОЛЕТАРСКИЙ» +7 (999) 775-18-25\n"
        "2. 📍 Заречье: ул. Максима Горького, д.35а +7 (953) 972-66-85\n"
        "3. 📍 Центр: ул. Каминского, д.4Б +7 (952) 018-54-72\n"
        "4. 📍 Советский: Красноармейский пр-т, д.19, ТЦ «ФАБРИКАНТ» +7 (902) 697-88-58\n"
        "5. 📍 Центр: ул. 9-мая д.2, «SPAR» +7 (953) 962-53-77\n"
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
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex("^📱 Оставить заявку$"), start_form),
        ],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition)],
            KIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, kit)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, district)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    telegram_app.add_handler(conv_handler)
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ℹ️ О нас$"), about))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏬 Адреса и контакты$"), contacts))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📱 Оставить заявку$"), start_form))
    telegram_app.add_handler(MessageHandler(filters.ALL, help_command))
    telegram_app.add_handler(CommandHandler("cancel", cancel))
    telegram_app.add_handler(MessageHandler(filters.ALL, help_command))

    telegram_app.add_handler(
        CallbackQueryHandler(start_form_callback, pattern="^start_form$")
    )

    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{APP_URL}/{WEBHOOK_SECRET}"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
