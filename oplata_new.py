import json
import os
import time
import requests
import uuid
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import BadRequest

# Определение состояний
CHOOSING_SERVICE, AWAITING_PAYMENT, AWAITING_SCREENSHOT = range(3)

# Инициализация базы данных (JSON файл)
def init_db():
    try:
        with open('payments.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def check_internet():
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False

def wait_for_internet(timeout=3600, interval=5):
    elapsed_time = 0
    while elapsed_time < timeout:
        if check_internet():
            print("Інтернет є, запускаємо бота.")
            return True
        print("Немає інтернету, перевіряємо знову через 5 секунд...")
        time.sleep(interval)
        elapsed_time += interval
    print("Інтернет не з’явився за 1 годину. Бот не буде запущено.")
    return False

def init_admin():
    try:
        with open('admin.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return None

def save_admin(admin_id):
    admin_data = {"admin_id": int(admin_id)}
    with open('admin.json', 'w', encoding='utf-8') as file:
        json.dump(admin_data, file, ensure_ascii=False, indent=4)

# Сохранение фото в базу данных
def save_screenshot(user_data, file_path, db):
    unique_key = str(uuid.uuid4())
    db[unique_key] = {
        "file_name": os.path.basename(file_path),
        "user_id": user_data.id,
        "username": user_data.username,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name
    }
    with open('payments.json', 'w', encoding='utf-8') as file:
        json.dump(db, file, ensure_ascii=False, indent=4)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    await update.message.reply_text(
        f'Привет, @{user.username}! Выберите услугу (для отмены напишите /cancel):',
        reply_markup=ReplyKeyboardMarkup(
            [['Переустановка винды💯❣️', 'Переустановка драйверов♻️✅'],
             ['Проверка ПК на вирусы🛅🛜', 'Диагностика ошибок✅❇️🌐'],
             ['Оптимизация FPS в играх💸💵', 'Ускорение интернета🛜🛜'],
             ['Блокировка рекламы🔒', 'Установка нужных программ📂']],
            one_time_keyboard=True, resize_keyboard=True
        )
    )
    return CHOOSING_SERVICE

# Выбор услуги
async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['service'] = update.message.text
    await update.message.reply_text(
        f"Вы выбрали: {update.message.text}. Номер карты (4441111140152400) Переведите нужную сумму и напишите 'Сделал'."
    )
    return AWAITING_PAYMENT

# Подтверждение платежа
async def payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() in ['сделал', 'сделала']:
        await update.message.reply_text("Отправьте фото подтверждения перевода.")
        return AWAITING_SCREENSHOT
    else:
        await update.message.reply_text("Напишите 'Сделал' после перевода.")
        return AWAITING_PAYMENT

# Обработка фото
async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    photo = update.message.photo[-1]
    file_id = photo.file_id
    bot = context.bot

    try:
        file = await bot.get_file(file_id)

        # Создаем папку для сохранения
        os.makedirs("payments", exist_ok=True)

        # Генерируем уникальное имя файла
        file_path = os.path.join("payments", f"{uuid.uuid4()}.jpg")
        await file.download_to_drive(file_path)

        # Сохранение в базу данных
        db = init_db()
        save_screenshot(user, file_path, db)

        # Отправка администратору
        admin_data = init_admin()
        admin_chat_id = admin_data.get("admin_id") if admin_data else None

        if admin_chat_id:
            await bot.send_photo(
                chat_id=admin_chat_id,
                photo=open(file_path, 'rb'),
                caption=f"Платеж от @{user.username} ({user.id})\nУслуга: {context.user_data['service']}"
            )
            await update.message.reply_text("Фото отправлено на проверку. Ждите ответа.")
        else:
            await update.message.reply_text("Администратор не настроен. Обратитесь к разработчику.")
    
    except Exception as e:
        await update.message.reply_text(f"Ошибка загрузки фото: {e}. Попробуйте снова.")
    
    return ConversationHandler.END

# Команда /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

# Команда /set_admin
async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id == 7413915232:  # Замените на свой ID
        if context.args:
            admin_id = context.args[0]
            save_admin(admin_id)
            await update.message.reply_text(f"ID администратора установлен: {admin_id}")
        else:
            await update.message.reply_text("Укажите ID администратора.")
    else:
        await update.message.reply_text("У вас нет прав.")

# Команда /get_requests
async def get_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    admin_data = init_admin()

    if admin_data and user.id == admin_data.get("admin_id"):
        db = init_db()
        if db:
            for key, data in db.items():
                text = (f"Запрос от @{data['username']}:\n"
                        f"Имя: {data['first_name']} {data['last_name']}\n"
                        f"Фото: {data['file_name']}\n")
                
                # Путь к файлу изображения
                file_path = os.path.join("payments", data["file_name"])
                
                # Проверка существования файла перед отправкой
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as photo_file:
                        await context.bot.send_photo(chat_id=user.id, photo=photo_file, caption=text)
                else:
                    await context.bot.send_message(chat_id=user.id, text=f"Фото для запроса @{data['username']} не найдено.")
        else:
            await update.message.reply_text("Нет запросов.")
    else:
        await update.message.reply_text("У вас нет прав.")

# Запуск бота
def main():
    if not check_internet():
        print("Немає інтернету, чекаємо підключення...")
        if not wait_for_internet(timeout=3600, interval=5):  # 1 година (3600 секунд)
            print("Інтернет не з'явився. Завершення.")
            return

    try:
        # Создаем приложение с токеном
        application = Application.builder().token("7924462550:AAFbto82v8sNLEt0SbNeYAyvr4QHMyohbks").build()

        # Настраиваем ConversationHandler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                CHOOSING_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_service)],
                AWAITING_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_confirmation)],
                AWAITING_SCREENSHOT: [MessageHandler(filters.PHOTO, screenshot_handler)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        # Добавляем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('set_admin', set_admin))
        application.add_handler(CommandHandler('get_requests', get_requests))

        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Виникла помилка: {e}")

if __name__ == '__main__':
    main()
