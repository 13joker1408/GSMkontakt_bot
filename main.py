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
import asyncio
from functools import wraps

load_dotenv()

# Подключение к MongoDB с оптимизированными настройками
client = MongoClient(
    os.getenv("MONGODB_URI"),
    maxPoolSize=10,  # Ограничиваем пул соединений
    minPoolSize=1,
    maxIdleTimeMS=30000,  # 30 сек
    serverSelectionTimeoutMS=5000,  # 5 сек таймаут
    socketTimeoutMS=10000  # 10 сек таймаут сокета
)
db = client[os.getenv("MONGO_DB_NAME")]
users_collection = db[os.getenv("MONGO_COLLECTION_NAME")]

# Создаем индекс для быстрого поиска по user_id (если не существует)
try:
    users_collection.create_index("user_id", unique=True)
except Exception as e:
    print(f"Индекс уже существует или ошибка создания: {e}")

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

# Декоратор для асинхронного выполнения операций с БД
def run_in_executor(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper

# Асинхронные функции для работы с БД
@run_in_executor
def save_user_to_db(user_id, username, full_name):
    try:
        print(f"🔄 Попытка сохранить пользователя: ID={user_id}, Name={full_name}, Username={username}")
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "full_name": full_name
            }},
            upsert=True
        )
        
        print(f"✅ Пользователь сохранен: matched={result.matched_count}, modified={result.modified_count}, upserted_id={result.upserted_id}")
        
        # Проверяем, что пользователь действительно сохранился
        saved_user = users_collection.find_one({"user_id": user_id})
        if saved_user:
            print(f"✅ Подтверждение: пользователь найден в БД: {saved_user}")
            return True
        else:
            print(f"❌ Пользователь не найден в БД после сохранения!")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")
        import traceback
        traceback.print_exc()
        return False

@run_in_executor
def get_users_from_db():
    try:
        print(f"🔍 Поиск пользователей в коллекции: {users_collection.name}")
        
        # Проверяем общее количество документов
        total_count = users_collection.count_documents({})
        print(f"🔍 Всего документов в коллекции: {total_count}")
        
        users_cursor = users_collection.find(
            {}, 
            {"_id": 0, "user_id": 1, "username": 1, "full_name": 1}
        ).limit(100)
        
        users_list = list(users_cursor)
        print(f"🔍 Получено пользователей: {len(users_list)}")
        
        # Выводим первых нескольких пользователей для диагностики
        for i, user in enumerate(users_list[:3]):
            print(f"🔍 Пользователь {i+1}: {user}")
            
        return users_list
    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        import traceback
        traceback.print_exc()
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    full_name = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()

    print(f"🔄 Обработка /start от пользователя: ID={user_id}, Name={full_name}, Username={username}")
    
    # Сохраняем пользователя синхронно, чтобы убедиться, что он сохранился
    try:
        save_result = await save_user_to_db(user_id, username, full_name)
        print(f"🔄 Результат сохранения: {save_result}")
    except Exception as e:
        print(f"❌ Исключение при сохранении: {e}")
    
    # Отвечаем пользователю
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

        # Отправляем сообщение админу асинхронно
        asyncio.create_task(context.bot.send_message(chat_id=ADMIN_ID, text=summary))
        
        # Сразу отвечаем пользователю
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
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    # Сначала отправляем сообщение о загрузке
    loading_message = await update.message.reply_text("⏳ Загружаю список пользователей...")
    
    try:
        # Асинхронно получаем пользователей
        users_list_data = await get_users_from_db()
        
        if not users_list_data:
            await loading_message.edit_text("👥 Пользователей не найдено в базе данных.")
            return

        user_lines = []
        for i, user in enumerate(users_list_data[:50], 1):  # Показываем только первые 50
            username = user.get('username', '-')
            full_name = user.get('full_name', '-')
            user_id_str = user.get('user_id', '-')
            
            line = f"{i}. ID: {user_id_str}, Имя: {full_name}, Username: @{username if username != '-' else 'не указан'}"
            user_lines.append(line)

        message = f"👥 Список пользователей (показано {len(user_lines)} из {len(users_list_data)}):\n\n" + "\n".join(user_lines)
        
        # Ограничение Telegram на длину сообщения
        if len(message) > 4000:
            message = message[:4000] + "\n\n...список обрезан."

        await loading_message.edit_text(message)
        
    except Exception as e:
        print(f"❌ Ошибка при получении списка пользователей: {e}")
        await loading_message.edit_text("❌ Произошла ошибка при получении списка пользователей.")

async def debug_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки БД (только для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    try:
        # Проверяем подключение
        client.admin.command('ping')
        
        # Получаем статистику коллекции
        total_docs = users_collection.count_documents({})
        
        # Получаем несколько записей
        sample_users = list(users_collection.find({}).limit(5))
        
        debug_info = f"🔧 Отладка БД:\n\n"
        debug_info += f"✅ MongoDB подключение: OK\n"
        debug_info += f"📊 База: {db.name}\n"
        debug_info += f"📊 Коллекция: {users_collection.name}\n"
        debug_info += f"📊 Всего документов: {total_docs}\n\n"
        
        if sample_users:
            debug_info += f"👥 Примеры записей:\n"
            for i, user in enumerate(sample_users, 1):
                debug_info += f"{i}. ID: {user.get('user_id')}, Name: {user.get('full_name')}\n"
        else:
            debug_info += "❌ Записей не найдено"
            
        await update.message.reply_text(debug_info)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отладки БД: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📌 Как работает бот:\n\n"
        "Нажми кнопку '📱 Оставить заявку', чтобы отправить информацию о технике, которую хочешь продать.\n"
        "Также ты можешь узнать адреса магазинов и контакты, используя соответствующие кнопки."
    )
    
    # Добавляем команды для админа
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        help_text += "\n\n🔧 Команды админа:\n/debug_db - проверить БД"
    
    await update.message.reply_text(help_text)

# Упрощенная функция для неизвестных сообщений
async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

    # Проверяем подключение к MongoDB при запуске
    try:
        # Пингуем MongoDB
        client.admin.command('ping')
        print("✅ MongoDB подключение успешно")
        
        # Проверяем доступ к коллекции
        print(f"🔍 База данных: {db.name}")
        print(f"🔍 Коллекция: {users_collection.name}")
        print(f"🔍 Количество документов в коллекции: {users_collection.count_documents({})}")
        
        # Выводим несколько существующих записей
        existing_users = list(users_collection.find({}).limit(3))
        print(f"🔍 Существующие пользователи: {existing_users}")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к MongoDB: {e}")
        import traceback
        traceback.print_exc()

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

    # Добавляем обработчики
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("debug_db", debug_db))
    telegram_app.add_handler(conv_handler)
    
    # Обработчики кнопок меню
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ℹ️ О нас$"), about))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏬 Адреса и контакты$"), contacts))
    telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👥 Пользователи$"), users_list))
    
    # Обработчик неизвестных сообщений (последний!)
    telegram_app.add_handler(MessageHandler(filters.TEXT, handle_unknown_message))

    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{APP_URL}/{WEBHOOK_SECRET}"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
    print(f"🔑 ADMIN_ID установлен: {ADMIN_ID}")