from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

MODEL, CONDITION, KIT, DISTRICT, PHONE = range(5)

# Пример стартового сообщения с кнопками
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📱 Оставить заявку")],
        [KeyboardButton("ℹ️ О нас"), KeyboardButton("🏬 Адреса и контакты")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=reply_markup)

# Обработчики для ConversationHandler
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вы выбрали оставить заявку. Выберите модель:")
    return MODEL

async def model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Вы выбрали модель: {update.message.text}. Теперь условие:")
    return CONDITION

async def condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Условие: {update.message.text}. Теперь комплект:")
    return KIT

async def kit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Комплект: {update.message.text}. Теперь район:")
    return DISTRICT

async def district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Район: {update.message.text}. Теперь номер телефона:")
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact.phone_number if update.message.contact else update.message.text
    await update.message.reply_text(f"Спасибо! Ваш телефон: {contact}. Заявка принята.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отмена заявки.")
    return ConversationHandler.END

# Обработчики для кнопок "ℹ️ О нас" и "🏬 Адреса и контакты"
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Это информация о нас.")

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Наши адреса и контакты: ...")

if __name__ == "__main__":
    APP_URL = "https://yourdomain.com"
    WEBHOOK_SECRET = "some_secret"

    telegram_app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    # Добавляем сначала обработчики кнопок с текстом
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.Regex("^ℹ️ О нас$") & filters.TEXT, about))
    telegram_app.add_handler(MessageHandler(filters.Regex("^🏬 Адреса и контакты$") & filters.TEXT, contacts))

    # Затем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📱 Оставить заявку$") & filters.TEXT, start_form)],
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

    # Запуск (для webhook, например)
    import asyncio

    async def main():
        await telegram_app.initialize()
        await telegram_app.start()
        webhook_url = f"{APP_URL}/{WEBHOOK_SECRET}"
        await telegram_app.bot.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
        # Ждём, чтобы приложение не завершилось сразу
        await telegram_app.updater.idle()

    asyncio.run(main())
