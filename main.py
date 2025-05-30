import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pymongo import MongoClient
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# Подключение к MongoDB
client = MongoClient(os.getenv("MONGODB_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
users_collection = db[os.getenv("MONGO_COLLECTION_NAME")]

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
    [KeyboardButton("📱 Оставить заявку")],
    [KeyboardButton("ℹ️ О нас")],
    [KeyboardButton("🏬 Адреса и контакты")]
]

admin_menu_keyboard = main_menu_keyboard + [[KeyboardButton("👥 Пользователи")]]

main_menu = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
admin_menu = ReplyKeyboardMarkup(admin_menu_keyboard, resize_keyboard=True)

app = FastAPI()
telegram_app: Application = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    full_name = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()

    # Сохраняем пользователя в базе данных
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "full_name": full_name
            }},
            upsert=True
        )
        print(f"✅ Пользователь сохранен: ID={user_id}, Name={full_name}")
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")
    
    # Проверяем, является ли пользователь администратором
    print(f"🔍 Проверка админа: user_id={user_id}, ADMIN_ID={ADMIN_ID}, равны={user_id == ADMIN_ID}")
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("🔑 Добро пожаловать, администратор! Выбери действие:", reply_markup=admin_menu)
    else:
        await update.message.reply_text("👋 Добро пожаловать! Выбери действие:", reply_markup=main_menu)
        
    return ConversationHandler.END

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши модель твоей техники:", reply_markup=ReplyKeyboardRemove())
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
        
        # Возвращаем правильное меню в зависимости от пользователя
        user_id = update.effective_user.id
        menu = admin_menu if user_id == ADMIN_ID else main_menu
        await update.message.reply_text("Спасибо! Мы скоро свяжемся с тобой.", reply_markup=menu)
        return ConversationHandler.END
    else:
        contact_button = KeyboardButton("📞 Отправить номер", request_contact=True)
        keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Пожалуйста, нажми кнопку ниже, чтобы мы могли с тобой связаться:", reply_markup=keyboard)
        return PHONE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    menu = admin_menu if user_id == ADMIN_ID else main_menu
    await update.message.reply_text("Заявка отменена.", reply_markup=menu)
    return ConversationHandler.END

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Мы — скупка цифровой техники с 2013 года.\n"
        "Принимаем смартфоны, ноутбуки, планшеты. Оценка за 5 минут!\n"
        "Принимаем только полностью рабочую технику"
    )

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏬 <b>Наши адреса и телефоны:</b>\n\n"
        "1. 🏠 <b>Заречье:</b> <a href='https://yandex.ru/maps/org/gsmkontakt/1276292498/'>ул. Максима Горького, д.35а</a>\n"
        "   📞 +7-953-972-66-85\n\n"
        "2. 🏠 <b>Пролетарский:</b> <a href='https://yandex.ru/maps/org/gsmkontakt/1294592969/'>ул. Ложевая, д.125а, ТЦ «ПРОЛЕТАРСКИЙ»</a>\n"
        "   📞 +7-999-775-18-25\n\n"
        "3. 🏠 <b>Центр:</b> <a href='https://yandex.ru/maps/org/gsmkontakt/1650827512/'>ул. Каминского, д.4Б</a>\n"
        "   📞 +7-952-018-54-72\n\n"
        "4. 🏠 <b>Советский:</b> <a href='https://yandex.ru/maps/org/gsmkontakt/107114858592/'>ул. 9 мая, д.2, «SPAR»</a>\n"
        "   📞 +7-953-962-53-77\n\n"
        "5. 🏠 <b>Советский:</b> <a href='https://yandex.ru/maps/org/gsmkontakt/1933915362/'>Красноармейский пр-т, д.19, ТЦ «ФАБРИКАНТ»</a>\n"
        "   📞 +7-902-697-88-58\n\n"
        "📞 <b>Телефон горячей линии:</b> +7-800-302-20-71\n\n"
        "🌐 <b>Сайт:</b> gsmkontakt.ru\n"
        "📱 <b>Telegram:</b> @Strjke",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"🔍 Запрос списка пользователей от: user_id={user_id}, ADMIN_ID={ADMIN_ID}")
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    try:
        # Получаем всех пользователей из базы данных
        users_cursor = users_collection.find({}, {"_id": 0, "user_id": 1, "username": 1, "full_name": 1})
        users_list = list(users_cursor)
        
        print(f"🔍 Найдено пользователей в БД: {len(users_list)}")
        
        if not users_list:
            await update.message.reply_text("👥 Пользователей не найдено в базе данных.")
            return

        user_lines = []
        for i, user in enumerate(users_list, 1):
            username = user.get('username', '-')
            full_name = user.get('full_name', '-')
            user_id_str = user.get('user_id', '-')
            
            line = f"{i}. ID: {user_id_str}\n   Имя: {full_name}\n   Username: @{username if username != '-' else 'не указан'}"
            user_lines.append(line)

        message = f"👥 Список пользователей ({len(users_list)} чел.):\n\n" + "\n\n".join(user_lines)
        
        # Ограничение Telegram на длину сообщения
        if len(message) > 4000:
            message = message[:4000] + "\n\n...список слишком длинный, показаны первые пользователи."

        await update.message.reply_text(message)
        
    except Exception as e:
        print(f"❌ Ошибка при получении списка пользователей: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении списка пользователей.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Как работает бот:\n\n"
        "Нажми кнопку '📱 Оставить заявку', чтобы отправить информацию о технике, которую хочешь продать.\n"
        "Также ты можешь узнать адреса магазинов и контакты, используя соответствующие кнопки."
    )

# Функция для обработки неизвестных сообщений
async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text if update.message and update.message.text else ""
    
    print(f"🔍 Неизвестное сообщение от {user_id}: '{message_text}'")
    
    # Возвращаем правильное меню
    menu = admin_menu if user_id == ADMIN_ID else main_menu
    await update.message.reply_text(
        "❓ Не понимаю эту команду. Воспользуйтесь кнопками меню:",
        reply_markup=menu
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

    # ConversationHandler для заявок
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^📱 Оставить заявку$"), start_form)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition)],
            KIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, kit)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, district)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    # Добавляем обработчики в правильном порядке
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(conv_handler)
    
    # Обработчики кнопок меню
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ℹ️ О нас$"), about))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏬 Адреса и контакты$"), contacts))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👥 Пользователи$"), users_list))
    
    # Обработчик неизвестных сообщений (должен быть последним!)
    telegram_app.add_handler(MessageHandler(filters.TEXT, handle_unknown_message))

    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{APP_URL}/{WEBHOOK_SECRET}"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
    print(f"🔑 ADMIN_ID установлен: {ADMIN_ID}")