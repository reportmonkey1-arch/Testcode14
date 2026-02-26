import logging
import random
import sqlite3
import asyncio
import aiohttp
import json
import os
import shutil
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
PIZZA_EMOJI = "🍕"
LOADING_BAR = ["⬜️⬜️⬜️⬜️⬜️", "🟩⬜️⬜️⬜️⬜️", "🟩🟩⬜️⬜️⬜️", "🟩🟩🟩⬜️⬜️", "🟩🟩🟩🟩⬜️", "🟩🟩🟩🟩🟩"]
ADMIN_IDS = [7662435450]  # Замените на ваши ID

# Множество каналов для подписки (ID и ссылки)
REQUIRED_CHANNELS = {
    "-1003744715168": "https://t.me/+rBaVlTn8eLphY2Vi",  # Основной канал
    "-1002463840734": "https://t.me/GhostChannelNoScam",
    # Добавьте дополнительные каналы по необходимости
    # "-CHANNEL_ID": "https://t.me/channel_link",
}

CHANNEL_LINK = "https://t.me/GhostChannelNoScam"  # Основная ссылка (для обратной совместимости)
LOG_CHAT_ID = "-5135007259"  # Замените на ID чата для логов
CRYPTO_BOT_TOKEN = "539597:AAdmbtlwLwFx7CIbL1NWeNVMufXQ6f6Qy99"  # Замените на токен CryptoBot
REQUIRED_NAME = "@TestScriptUujUuBwowowksj_bot"  # Требуемая часть в отображаемом имени для активации промокода
MANUAL_LINK = "https://teletype.in/@logunovproduct1/ManualDodoPizzaLG"  # Ссылка на мануал
DB_BACKUP_PATH = "bot_backup.db"  # Путь для резервной копии БД

# Цены в USDT
PRICES = {
    "1_day": 1,
    "3_days": 2.5,
    "1_week": 5,
    "1_month": 15,
    "forever": 25
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        status TEXT,
        subscription INTEGER,
        banned INTEGER,
        subscribed INTEGER,
        last_activity TEXT,
        last_pizza_time TEXT,
        pizza_count INTEGER DEFAULT 0,
        read_manual INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        currency TEXT,
        plan TEXT,
        status TEXT,
        timestamp TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sent_pizzas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        address TEXT,
        timestamp TEXT,
        UNIQUE(user_id, address)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        days INTEGER,
        max_activations INTEGER,
        activations_left INTEGER,
        created_by INTEGER,
        created_at TEXT,
        description TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        promo_code TEXT,
        activated_at TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Функции для работы с базой данных
def get_user(user_id):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {
            "user_id": user[0],
            "username": user[1],
            "status": user[2],
            "subscription": user[3],
            "banned": bool(user[4]),
            "subscribed": bool(user[5]),
            "last_activity": user[6],
            "last_pizza_time": user[7],
            "pizza_count": user[8] if user[8] else 0,
            "read_manual": bool(user[9]) if len(user) > 9 else False
        }
    return None

def update_user(user_id, data):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO users 
    (user_id, username, status, subscription, banned, subscribed, last_activity, last_pizza_time, pizza_count, read_manual) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data.get("username", ""),
        data.get("status", "👤 Пользователь"),
        data.get("subscription", 0),
        int(data.get("banned", False)),
        int(data.get("subscribed", False)),
        data.get("last_activity", datetime.now().isoformat()),
        data.get("last_pizza_time", ""),
        data.get("pizza_count", 0),
        int(data.get("read_manual", False))
    ))
    
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return users

def add_sent_pizza(user_id, address):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO sent_pizzas (user_id, address, timestamp)
        VALUES (?, ?, ?)
        ''', (user_id, address, datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def has_sent_to_address(user_id, address):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 1 FROM sent_pizzas WHERE user_id = ? AND address = ?
    ''', (user_id, address))
    
    result = cursor.fetchone() is not None
    conn.close()
    return result

def create_promo_code(code, days, max_activations, created_by, description=""):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO promo_codes (code, days, max_activations, activations_left, created_by, created_at, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (code, days, max_activations, max_activations, created_by, datetime.now().isoformat(), description))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_promo_code(code):
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM promo_codes WHERE code = ?', (code,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "code": row[0],
            "days": row[1],
            "max_activations": row[2],
            "activations_left": row[3],
            "created_by": row[4],
            "created_at": row[5],
            "description": row[6]
        }
    return None

def activate_promo_code(user_id, code):
    conn = None
    try:
        conn = sqlite3.connect('bot.db', timeout=10)
        cursor = conn.cursor()
        
        cursor.execute('BEGIN IMMEDIATE')
        
        cursor.execute('SELECT 1 FROM promo_activations WHERE user_id = ? AND promo_code = ?', (user_id, code))
        if cursor.fetchone():
            conn.rollback()
            return False, "Вы уже активировали этот промокод"
        
        cursor.execute('SELECT * FROM promo_codes WHERE code = ?', (code,))
        row = cursor.fetchone()
        
        if not row:
            conn.rollback()
            return False, "Промокод не найден"
        
        promo = {
            "code": row[0],
            "days": row[1],
            "max_activations": row[2],
            "activations_left": row[3],
            "created_by": row[4],
            "created_at": row[5],
            "description": row[6]
        }
        
        if promo["activations_left"] <= 0:
            conn.rollback()
            return False, "Лимит активаций исчерпан"
        
        cursor.execute('''
        UPDATE promo_codes 
        SET activations_left = activations_left - 1 
        WHERE code = ? AND activations_left > 0
        ''', (code,))
        
        if cursor.rowcount == 0:
            conn.rollback()
            return False, "Лимит активаций исчерпан"
        
        cursor.execute('''
        INSERT INTO promo_activations (user_id, promo_code, activated_at)
        VALUES (?, ?, ?)
        ''', (user_id, code, datetime.now().isoformat()))
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        
        if user_row:
            user = {
                "user_id": user_row[0],
                "username": user_row[1],
                "status": user_row[2],
                "subscription": user_row[3],
                "banned": bool(user_row[4]),
                "subscribed": bool(user_row[5]),
                "last_activity": user_row[6],
                "last_pizza_time": user_row[7],
                "pizza_count": user_row[8] if user_row[8] else 0,
                "read_manual": bool(user_row[9]) if len(user_row) > 9 else False
            }
        else:
            user = {
                "user_id": user_id,
                "username": "",
                "status": "👤 Пользователь",
                "subscription": 0,
                "banned": False,
                "subscribed": False,
                "last_activity": datetime.now().isoformat(),
                "last_pizza_time": "",
                "pizza_count": 0,
                "read_manual": False
            }
        
        new_subscription = max(
            datetime.now().timestamp() + (promo["days"] * 86400),
            user["subscription"] if user and user["subscription"] > datetime.now().timestamp() else 0
        )
        
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, status, subscription, banned, subscribed, last_activity, last_pizza_time, pizza_count, read_manual) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user["user_id"],
            user["username"],
            user["status"],
            new_subscription,
            int(user["banned"]),
            int(user["subscribed"]),
            user["last_activity"],
            user["last_pizza_time"],
            user["pizza_count"],
            int(user["read_manual"])
        ))
        
        conn.commit()
        return True, f"Промокод активирован! Получено {promo['days']} дней подписки"
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка активации промокода: {e}")
        return False, "Произошла ошибка при активации промокода"
    finally:
        if conn:
            conn.close()

def get_all_promo_codes():
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT code, days, max_activations, activations_left, created_by, created_at, description 
    FROM promo_codes
    ''')
    
    promos = []
    for row in cursor.fetchall():
        promos.append({
            "code": row[0],
            "days": row[1],
            "max_activations": row[2],
            "activations_left": row[3],
            "created_by": row[4],
            "created_at": row[5],
            "description": row[6]
        })
    
    conn.close()
    return promos

# Функции для работы с резервными копиями БД
def backup_db():
    try:
        shutil.copy2('bot.db', DB_BACKUP_PATH)
        return True
    except Exception as e:
        logger.error(f"Ошибка создания резервной копии БД: {e}")
        return False

def restore_db():
    try:
        if os.path.exists(DB_BACKUP_PATH):
            shutil.copy2(DB_BACKUP_PATH, 'bot.db')
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка восстановления БД: {e}")
        return False

def clear_db():
    try:
        conn = sqlite3.connect('bot.db', timeout=10)
        cursor = conn.cursor()
        
        # Удаляем все таблицы
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS payments")
        cursor.execute("DROP TABLE IF EXISTS sent_pizzas")
        cursor.execute("DROP TABLE IF EXISTS promo_codes")
        cursor.execute("DROP TABLE IF EXISTS promo_activations")
        
        # Создаем заново пустые таблицы
        init_db()
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки БД: {e}")
        return False

# Функции для работы с CryptoBot API
async def create_crypto_invoice(amount: float, user_id: int, plan: str) -> dict:
    url = f"https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Оплата подписки на {plan.replace('_', ' ')}",
        "hidden_message": f"Пользователь: {user_id}\nТариф: {plan}",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/TestScriptUujUuBwowowksj_bot",
        "payload": json.dumps({
            "user_id": user_id,
            "plan": plan
        })
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            if response.status == 200 and result.get("ok"):
                return result.get("result")
            else:
                logger.error(f"Ошибка создания инвойса: {result}")
                return None

async def check_crypto_invoice(invoice_id: str) -> dict:
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            result = await response.json()
            if response.status == 200 and result.get("ok"):
                invoices = result.get("result", {}).get("items", [])
                return invoices[0] if invoices else None
            else:
                logger.error(f"Ошибка проверки инвойса: {result}")
                return None

async def send_log_message(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        clean_text = text.replace("*", "").replace("`", "").replace("_", "")
        await context.bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=clean_text,
            parse_mode=None
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение в лог-чат {LOG_CHAT_ID}: {e}")

# Функции для работы с каналами
async def check_all_subscriptions(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        unsubscribed_channels = []
        for channel_id in REQUIRED_CHANNELS.keys():
            try:
                member = await context.bot.get_chat_member(channel_id, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    unsubscribed_channels.append(channel_id)
            except Exception as e:
                logger.error(f"Ошибка проверки подписки на канал {channel_id}: {e}")
                unsubscribed_channels.append(channel_id)
        
        if not unsubscribed_channels:
            user = get_user(user_id) or {}
            user['subscribed'] = True
            update_user(user_id, user)
            return True
        else:
            user = get_user(user_id) or {}
            user['subscribed'] = False
            update_user(user_id, user)
            return False
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

async def get_unsubscribed_channels(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        unsubscribed = []
        for channel_id, channel_link in REQUIRED_CHANNELS.items():
            try:
                member = await context.bot.get_chat_member(channel_id, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    unsubscribed.append(channel_link)
            except Exception as e:
                logger.error(f"Ошибка проверки подписки на канал {channel_id}: {e}")
                unsubscribed.append(channel_link)
        return unsubscribed
    except Exception as e:
        logger.error(f"Ошибка получения списка неподписанных каналов: {e}")
        return []

async def ask_for_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        logger.warning("Попытка запроса подписки без пользователя")
        return
    
    user_id = update.effective_user.id
    unsubscribed = await get_unsubscribed_channels(context, user_id)
    
    if not unsubscribed:
        await send_main_menu(update, context)
        return
    
    keyboard = []
    for channel_link in unsubscribed:
        keyboard.append([InlineKeyboardButton(f"📢 Подписаться на канал", url=channel_link)])
    
    keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')])
    
    text = (
        "📢 *Пожалуйста, подпишитесь на наши каналы, чтобы использовать бота!*\n\n"
        "После подписки нажмите кнопку *\"Я подписался\"* для проверки."
    )
    
    try:
        if update.callback_query:
            query = update.callback_query
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка запроса подписки: {e}")

# Основные функции бота
async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    if not update.effective_user:
        logger.warning("Попытка отправить меню без пользователя")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await start(update, context)
        return
    
    if user.get('banned'):
        await context.bot.send_message(
            chat_id=user_id,
            text="⛔ Вы заблокированы и не можете использовать этого бота."
        )
        return
    
    keyboard = []
    
    if user.get("subscription", 0) > datetime.now().timestamp():
        keyboard.append([InlineKeyboardButton(f"{PIZZA_EMOJI} Отправить пиццу", callback_data='send_pizza')])
    else:
        keyboard.append([InlineKeyboardButton(f"🍕Купить пиццу", callback_data='buy_pizza')])
    
    keyboard.append([InlineKeyboardButton("🐧Профиль", callback_data='profile')])
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("☠️Админ-панель", callback_data='admin_panel')])
    
    caption = text if text else "*🍕Logunov Pizza - Лучший сервис по отправке пиццы! Более тысячи клиентов выбирают наш сервис, только мы делаем такую вкусную,сочную пиццу.Быстрая доставка - Качественный заказ.* 🚀\n\nВыберите действие:"
    
    try:
        if update.callback_query:
            query = update.callback_query
            try:
                message = await query.edit_message_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except:
                message = await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        # Пытаемся закрепить сообщение
        try:
            await context.bot.pin_chat_message(
                chat_id=update.effective_chat.id,
                message_id=message.message_id,
                disable_notification=True
            )
        except Exception as e:
            logger.warning(f"Не удалось закрепить сообщение: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка отправки меню: {e}")

async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("1 день - 1 USDT", callback_data='pay_1_day')],
        [InlineKeyboardButton("3 дня - 2.5 USDT", callback_data='pay_3_days')],
        [InlineKeyboardButton("1 неделя - 5 USDT", callback_data='pay_1_week')],
        [InlineKeyboardButton("1 месяц - 15 USDT", callback_data='pay_1_month')],
        [InlineKeyboardButton("Навсегда - 25 USDT", callback_data='pay_forever')],
        [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        text="*💰 Выберите срок подписки:*\n\n"
             "1. *1 день* - 1 USDT\n"
             "2. *3 дня* - 2.5 USDT\n"
             "3. *1 неделя* - 5 USDT\n"
             "4. *1 месяц* - 15 USDT\n"
             "5. *Навсегда* - 25 USDT\n\n"
             "Оплата принимается в USDT (TRC20)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def create_payment_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, plan: str):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    amount = PRICES[plan]
    
    invoice = await create_crypto_invoice(amount, user_id, plan)
    
    if not invoice:
        await query.edit_message_text(
            text="❌ *Ошибка при создании платежа!*\n\nПожалуйста, попробуйте позже.",
            parse_mode="Markdown"
        )
        return
    
    pay_url = invoice.get("pay_url")
    invoice_id = invoice.get("invoice_id")
    
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_payment_{invoice_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='buy_pizza')]
    ]
    
    await query.edit_message_text(
        text=f"*💳 Оплата {amount} USDT*\n\n"
             f"Пожалуйста, оплатите *{amount} USDT* по ссылке ниже:\n\n"
             f"После оплаты нажмите кнопку *\"Я оплатил\"*.\n"
             f"Платеж будет обработан в течение нескольких минут.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE, invoice_id: str):
    query = update.callback_query
    await query.answer("Проверяем платеж...")
    
    invoice = await check_crypto_invoice(invoice_id)
    if not invoice:
        await query.edit_message_text(
            text="❌ *Не удалось проверить статус платежа!*\n\nПожалуйста, попробуйте позже.",
            parse_mode="Markdown"
        )
        return
    
    status = invoice.get("status")
    if status == "paid":
        user_id = int(json.loads(invoice.get("payload")).get("user_id"))
        plan = json.loads(invoice.get("payload")).get("plan")
        
        days_to_add = 0
        if plan == "1_day":
            days_to_add = 1
        elif plan == "3_days":
            days_to_add = 3
        elif plan == "1_week":
            days_to_add = 7
        elif plan == "1_month":
            days_to_add = 30
        elif plan == "forever":
            days_to_add = 36500
        
        user = get_user(user_id) or {}
        user["subscription"] = max(user.get("subscription", 0), datetime.now().timestamp()) + (days_to_add * 86400)
        update_user(user_id, user)
        
        log_text = (f"#payment #success\n\n"
                   f"Пользователь: {user_id}\n"
                   f"Тариф: {plan.replace('_', ' ')}\n"
                   f"Дней: {days_to_add}\n"
                   f"Сумма: {PRICES[plan]} USDT\n"
                   f"Инвойс: {invoice_id}")
        
        await send_log_message(context, log_text)
        
        await query.edit_message_text(
            text=f"✅ *Оплата подтверждена!*\n\n"
                 f"Ваш тариф: *{plan.replace('_', ' ')}*\n"
                 f"Срок действия: *{days_to_add} дней*\n\n"
                 f"Теперь вы можете отправлять пиццу!",
            parse_mode="Markdown"
        )
        
        await send_main_menu(update, context)
    else:
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить снова", callback_data=f'check_payment_{invoice_id}')],
            [InlineKeyboardButton("🔙 Назад", callback_data='buy_pizza')]
        ]
        await query.edit_message_text(
            text="⌛ *Платеж еще не получен!*\n\n"
                 "Если вы уже оплатили, пожалуйста, подождите несколько минут и проверьте снова.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def show_manual_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("read_manual"):
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
        await query.edit_message_text(
            text="*✏️ Введите адрес доставки:*\n"
                 "Обязательно укажите ссылку `https://t.me`\n\n"
                 "Пример: `https://t.me/like_avito_chat/4544578`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data['awaiting_address'] = True
        return
    
    keyboard = [
        [InlineKeyboardButton("📚 Открыть мануал", url=MANUAL_LINK)],
        [InlineKeyboardButton("✅ Я ознакомился", callback_data='confirm_manual')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        text="*📚 Для продолжения ознакомьтесь с мануалом и нажмите кнопку ниже*\n\n"
             "Пожалуйста, внимательно прочитайте маник перед отправкой пиццы.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def confirm_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    user["read_manual"] = True
    update_user(user_id, user)
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
    await query.edit_message_text(
        text="*✏️ Введите адрес доставки:*\n"
             "Обязательно укажите ссылку `https://t.me`\n\n"
             "Пример: `https://t.me/like_avito_chat/4544578`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data['awaiting_address'] = True

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        await start(update, context)
        return
    
    sub_status = "❌ Нет пиццы" if user["subscription"] <= datetime.now().timestamp() else f"✅ Пицца (до {datetime.fromtimestamp(user['subscription']).strftime('%d.%m.%Y %H:%M')})"
    keyboard = [
        [InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    
    try:
        await query.edit_message_text(
            text=f"*📊 Профиль*\n\n"
                 f"• *Статус:* `{user['status']}`\n"
                 f"• *Пицца:* `{sub_status}`\n"
                 f"• *Отправлено сегодня:* `{user.get('pizza_count', 0)}`\n"
                 f"• *ID:* `{user_id}`\n"
                 f"• *Username:* @{user.get('username', '')}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении профиля: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"*📊 Профиль*\n\n"
                 f"• *Статус:* `{user['status']}`\n"
                 f"• *Пицца:* `{sub_status}`\n"
                 f"• *Отправлено сегодня:* `{user.get('pizza_count', 0)}`\n"
                 f"• *ID:* `{user_id}`\n"
                 f"• *Username:* @{user.get('username', '')}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def show_take_sub_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню изъятия подписки с тремя вариантами"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❌ Забрать полностью", callback_data='take_sub_full')],
        [InlineKeyboardButton("📅 Забрать до даты", callback_data='take_sub_date')],
        [InlineKeyboardButton("🔥 Забрать у всех", callback_data='take_sub_all')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        text="*❌ Изъятие подписки*\n\n"
             "Выберите вариант изъятия подписки:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def take_subscription_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полностью забирает подписку у пользователя"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['admin_action'] = 'take_sub_full'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='take_sub')]]
    
    await query.edit_message_text(
        text="*❌ Полное изъятие подписки*\n\n"
             "Введите ID пользователя для полного изъятия подписки:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def take_subscription_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забирает подписку до определенной даты"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['admin_action'] = 'take_sub_date'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='take_sub')]]
    
    await query.edit_message_text(
        text="*📅 Изъятие подписки до даты*\n\n"
             "Введите ID пользователя и дату в формате ДД.ММ.ГГГГ через пробел:\n"
             "Пример: `123456789 31.12.2023`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def take_subscription_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забирает подписку у всех пользователей"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data='confirm_take_all')],
        [InlineKeyboardButton("🔙 Назад", callback_data='take_sub')]
    ]
    
    await query.edit_message_text(
        text="*🔥 Изъятие подписки у всех пользователей*\n\n"
             "Вы уверены, что хотите забрать подписку у ВСЕХ пользователей?\n"
             "Это действие нельзя отменить!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def confirm_take_subscription_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение изъятия подписки у всех пользователей"""
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('bot.db', timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE users 
        SET subscription = ? 
        WHERE subscription > ?
        ''', (datetime.now().timestamp(), datetime.now().timestamp()))
        
        affected_users = cursor.rowcount
        conn.commit()
        
        await query.edit_message_text(
            text=f"✅ *Подписка изъята у {affected_users} пользователей!*",
            parse_mode="Markdown"
        )
        
        log_text = (f"#admin_action #take_sub_all\n\n"
                   f"Админ: {query.from_user.id}\n"
                   f"Изъято подписок: {affected_users}")
        
        await send_log_message(context, log_text)
        
    except Exception as e:
        logger.error(f"Ошибка изъятия подписок у всех: {e}")
        await query.edit_message_text(
            text="❌ *Произошла ошибка при изъятии подписок!*",
            parse_mode="Markdown"
        )
    finally:
        conn.close()
    
    await send_main_menu(update, context)

async def show_db_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления базой данных"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🧹 Очистить БД", callback_data='clear_db')],
        [InlineKeyboardButton("🔄 Восстановить БД", callback_data='restore_db')],
        [InlineKeyboardButton("💾 Создать резервную копию", callback_data='backup_db')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        text="*🗄️ Управление базой данных*\n\n"
             "⚠️ Внимание! Эти действия нельзя отменить!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def confirm_clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение очистки базы данных"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, очистить", callback_data='confirm_clear_db')],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data='db_management')]
    ]
    
    await query.edit_message_text(
        text="*🧹 Очистка базы данных*\n\n"
             "Вы уверены, что хотите полностью очистить базу данных?\n"
             "Все пользователи, платежи и промокоды будут удалены!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def execute_clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет очистку базы данных"""
    query = update.callback_query
    await query.answer()
    
    if clear_db():
        await query.edit_message_text(
            text="✅ *База данных успешно очищена!*",
            parse_mode="Markdown"
        )
        
        log_text = (f"#admin_action #db_cleared\n\n"
                   f"Админ: {query.from_user.id}")
        
        await send_log_message(context, log_text)
    else:
        await query.edit_message_text(
            text="❌ *Ошибка при очистке базы данных!*",
            parse_mode="Markdown"
        )
    
    await send_main_menu(update, context)

async def execute_backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создает резервную копию базы данных"""
    query = update.callback_query
    await query.answer("Создаем резервную копию...")
    
    if backup_db():
        await query.edit_message_text(
            text="✅ *Резервная копия базы данных успешно создана!*",
            parse_mode="Markdown"
        )
        
        log_text = (f"#admin_action #db_backup\n\n"
                   f"Админ: {query.from_user.id}")
        
        await send_log_message(context, log_text)
    else:
        await query.edit_message_text(
            text="❌ *Ошибка при создании резервной копии!*",
            parse_mode="Markdown"
        )
    
    await send_main_menu(update, context)

async def execute_restore_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает базу данных из резервной копии"""
    query = update.callback_query
    await query.answer("Восстанавливаем базу данных...")
    
    if restore_db():
        await query.edit_message_text(
            text="✅ *База данных успешно восстановлена из резервной копии!*",
            parse_mode="Markdown"
        )
        
        log_text = (f"#admin_action #db_restored\n\n"
                   f"Админ: {query.from_user.id}")
        
        await send_log_message(context, log_text)
    else:
        await query.edit_message_text(
            text="❌ *Ошибка при восстановлении базы данных!*",
            parse_mode="Markdown"
        )
    
    await send_main_menu(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        logger.warning("Попытка запуска без пользователя")
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    user = get_user(user_id)
    
    if not user:
        new_user = {
            "username": username,
            "status": "👤 Пользователь",
            "subscription": 0,
            "banned": False,
            "subscribed": False,
            "last_activity": datetime.now().isoformat(),
            "last_pizza_time": "",
            "pizza_count": 0,
            "read_manual": False
        }
        update_user(user_id, new_user)
        await ask_for_subscriptions(update, context)
    else:
        if user.get('banned'):
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать этого бота.")
            return
            
        subscribed = await check_all_subscriptions(context, user_id)
        if not subscribed:
            await ask_for_subscriptions(update, context)
            return
        
        await send_main_menu(update, context)
    
    if user:
        user["username"] = username
        update_user(user_id, user)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user:
        logger.warning("Получен callback без данных")
        return
    
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await start(update, context)
        return

    if user.get('banned'):
        await query.edit_message_text("⛔ Вы заблокированы и не можете использовать этого бота.")
        return

    try:
        if query.data == 'check_subscription':
            subscribed = await check_all_subscriptions(context, user_id)
            if subscribed:
                await send_main_menu(update, context)
            else:
                unsubscribed = await get_unsubscribed_channels(context, user_id)
                text = "❌ *Вы не подписаны на все каналы!*\n\n"
                text += "Пожалуйста, подпишитесь на эти каналы:\n"
                text += "\n".join(f"- {link}" for link in unsubscribed)
                
                await query.edit_message_text(
                    text=text,
                    parse_mode="Markdown"
                )
                await ask_for_subscriptions(update, context)
        
        elif query.data == 'hide_message':
            try:
                await query.delete_message()
            except:
                await query.edit_message_text("Сообщение скрыто")
        
        elif query.data == 'send_pizza':
            if user.get("last_pizza_time"):
                last_time = datetime.fromisoformat(user["last_pizza_time"])
                time_since_last = datetime.now() - last_time
                if time_since_last < timedelta(minutes=10):
                    time_left = timedelta(minutes=10) - time_since_last
                    minutes = time_left.seconds // 60
                    seconds = time_left.seconds % 60
                    await query.edit_message_text(
                        text=f"⏳ *Подождите {minutes} минут {seconds} секунд перед следующей отправкой пиццы!*",
                        parse_mode="Markdown"
                    )
                    return
            
            if user.get("subscription", 0) <= datetime.now().timestamp():
                await query.edit_message_text(
                    text="❌ *У вас нет пиццы для отправки!*\n\nПриобретите пиццу, чтобы заказы осуществлялись.",
                    parse_mode="Markdown"
                )
                return
            
            await show_manual_confirmation(update, context)
        
        elif query.data == 'confirm_manual':
            await confirm_manual(update, context)
        
        elif query.data == 'buy_pizza':
            await show_payment_options(update, context)
        
        elif query.data.startswith('pay_'):
            plan = query.data[4:]
            await create_payment_invoice(update, context, plan)
        
        elif query.data.startswith('check_payment_'):
            invoice_id = query.data[14:]
            await check_payment_status(update, context, invoice_id)
        
        elif query.data == 'profile':
            await show_profile(update, context)

        elif query.data == 'activate_promo':
            user_full_name = update.effective_user.full_name or ""
            if REQUIRED_NAME.lower() not in user_full_name.lower():
                keyboard = [
                    [InlineKeyboardButton("🔙 Профиль", callback_data='profile')]
                ]
                await query.edit_message_text(
                    text=f"❌ *Для активации промокода добавьте {REQUIRED_NAME} в ник!*\n\n"
                         f"Добавьте в свой ник это, чтобы продолжить.\n"
                         f"*Пример: Venom @Logunovv_delivery_bot.*\n\n"
                         f"После изменения попробуйте ещё раз.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                context.user_data['awaiting_name_update'] = True
                return
            
            keyboard = [[InlineKeyboardButton("🔙 Профиль", callback_data='profile')]]
            await query.edit_message_text(
                text="*🎁 Активация промокода*\n\n"
                     "Введите промокод:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data['awaiting_promo'] = True

        elif query.data == 'admin_panel':
            if user_id in ADMIN_IDS:
                keyboard = [
                    [InlineKeyboardButton("🎁 Выдать подписку", callback_data='give_sub')],
                    [InlineKeyboardButton("❌ Изъятие подписки", callback_data='take_sub')],
                    [InlineKeyboardButton("🔒 Заблокировать", callback_data='ban_user')],
                    [InlineKeyboardButton("🔓 Разблокировать", callback_data='unban_user')],
                    [InlineKeyboardButton("📢 Рассылка", callback_data='broadcast')],
                    [InlineKeyboardButton("🎫 Создать промокод", callback_data='create_promo')],
                    [InlineKeyboardButton("🗄️ Управление БД", callback_data='db_management')],
                    [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
                    [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
                ]
                await query.edit_message_text(
                    text="*⚙️ Админ-панель*\n\n"
                         "Выберите действие:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    text="⛔ *Доступ запрещен!*",
                    parse_mode="Markdown"
                )

        elif query.data == 'take_sub':
            await show_take_sub_menu(update, context)
        
        elif query.data == 'take_sub_full':
            await take_subscription_full(update, context)
        
        elif query.data == 'take_sub_date':
            await take_subscription_date(update, context)
        
        elif query.data == 'take_sub_all':
            await take_subscription_all(update, context)
        
        elif query.data == 'confirm_take_all':
            await confirm_take_subscription_all(update, context)
        
        elif query.data == 'create_promo':
            if user_id in ADMIN_IDS:
                context.user_data['admin_action'] = 'create_promo'
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text="*🎫 Создание промокода*\n\n"
                         "Введите данные промокода в формате:\n"
                         "`код количество_дней максимальное_количество_активаций описание`\n\n"
                         "Пример: `SUMMER2023 30 10 Летняя акция`",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

        elif query.data == 'db_management':
            await show_db_management(update, context)
        
        elif query.data == 'clear_db':
            await confirm_clear_db(update, context)
        
        elif query.data == 'confirm_clear_db':
            await execute_clear_db(update, context)
        
        elif query.data == 'backup_db':
            await execute_backup_db(update, context)
        
        elif query.data == 'restore_db':
            await execute_restore_db(update, context)
        
        elif query.data == 'main_menu':
            await send_main_menu(update, context)

        elif query.data == 'give_sub':
            if user_id in ADMIN_IDS:
                context.user_data['admin_action'] = 'give_sub'
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text="*🎁 Выдача подписки*\n\n"
                         "Введите ID пользователя и количество дней через пробел:\n"
                         "Пример: `123456789 30`\n\n"
                         "Для вечной подписки укажите 36500 дней",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

        elif query.data == 'ban_user':
            if user_id in ADMIN_IDS:
                context.user_data['admin_action'] = 'ban_user'
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text="*🔒 Блокировка пользователя*\n\n"
                         "Введите ID пользователя для блокировки:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

        elif query.data == 'unban_user':
            if user_id in ADMIN_IDS:
                context.user_data['admin_action'] = 'unban_user'
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text="*🔓 Разблокировка пользователя*\n\n"
                         "Введите ID пользователя для разблокировки:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

        elif query.data == 'broadcast':
            if user_id in ADMIN_IDS:
                context.user_data['admin_action'] = 'broadcast'
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text="*📢 Введите сообщение для рассылки:*",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

        elif query.data == 'stats':
            if user_id in ADMIN_IDS:
                conn = sqlite3.connect('bot.db', timeout=10)
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM users WHERE subscribed = 1')
                subscribed_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM users WHERE subscription > ?', (datetime.now().timestamp(),))
                active_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
                banned_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM sent_pizzas WHERE date(timestamp) = date("now")')
                pizzas_today = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM promo_codes')
                promos_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM promo_activations')
                promos_activated = cursor.fetchone()[0]
                
                conn.close()
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]]
                await query.edit_message_text(
                    text=f"*📊 Статистика бота*\n\n"
                         f"• Всего пользователей: `{total_users}`\n"
                         f"• Подписавшихся на канал: `{subscribed_users}`\n"
                         f"• С активной подпиской: `{active_users}`\n"
                         f"• Заблокированных: `{banned_users}`\n"
                         f"• Пицц отправлено сегодня: `{pizzas_today}`\n"
                         f"• Промокодов создано: `{promos_count}`\n"
                         f"• Промокодов активировано: `{promos_activated}`",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        await send_main_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        logger.warning("Получено сообщение без пользователя или самого сообщения")
        return

    user_id = update.effective_user.id
    user = get_user(user_id)
    text = update.message.text

    if not user:
        new_user = {
            "username": update.effective_user.username or "",
            "status": "👤 Пользователь",
            "subscription": 0,
            "banned": False,
            "subscribed": False,
            "last_activity": datetime.now().isoformat(),
            "last_pizza_time": "",
            "pizza_count": 0,
            "read_manual": False
        }
        update_user(user_id, new_user)
        user = new_user
        await ask_for_subscriptions(update, context)
        return

    if user.get('banned'):
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать этого бота.")
        return

    try:
        if 'awaiting_address' in context.user_data:
            if user.get("subscription", 0) <= datetime.now().timestamp():
                await update.message.reply_text(
                    "❌ *Ваша подписка закончилась!*\n\nПриобретите новую подписку, чтобы заказы осуществлялись.",
                    parse_mode="Markdown"
                )
                del context.user_data['awaiting_address']
                return
                
            if text and "https://t.me/" in text:
                if has_sent_to_address(user_id, text):
                    await update.message.reply_text(
                        "❌ *Вы уже отправляли пиццу на этот адрес!*\n"
                        "Пожалуйста, выберите другой адрес для доставки.",
                        parse_mode="Markdown"
                    )
                    return
                
                if user.get("last_pizza_time"):
                    last_time = datetime.fromisoformat(user["last_pizza_time"])
                    time_since_last = datetime.now() - last_time
                    if time_since_last < timedelta(minutes=10):
                        time_left = timedelta(minutes=10) - time_since_last
                        minutes = time_left.seconds // 60
                        seconds = time_left.seconds % 60
                        await update.message.reply_text(
                            text=f"⏳ *Подождите {minutes} минут {seconds} секунд перед следующей отправкой пиццы!*",
                            parse_mode="Markdown"
                        )
                        return
                
                msg = await update.message.reply_text(
                    "🛵 *Пицца в пути!* Ожидайте...",
                    parse_mode="Markdown"
                )
                
                for i, progress in enumerate(LOADING_BAR, 1):
                    await msg.edit_text(
                        f"*🚀 Доставка:* {progress}\n"
                        f"*Статус:* {i * 20}% завершено",
                        parse_mode="Markdown"
                    )
                    await asyncio.sleep(1)
                
                await msg.edit_text(
                    f"*🚀 Доставка:* 🟩🟩🟩🟩🟩\n"
                    f"*Статус:* 120% завершено\n"
                    f"*Завершаем обработку заказа...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(10)
                
                pizzas_sent = random.randint(23, 300)
                
                user["pizza_count"] = user.get("pizza_count", 0) + 1
                user["last_pizza_time"] = datetime.now().isoformat()
                update_user(user_id, user)
                
                add_sent_pizza(user_id, text)
                
                await msg.edit_text(
                    f"*✅ Доставка завершена!* {PIZZA_EMOJI}\n"
                    f"Пицца доставлена по адресу:\n`{text}`\n\n"
                    f"*Отправлено {pizzas_sent} пицц!*\n"
                    f"_Приятного аппетита!_ 😋",
                    parse_mode="Markdown"
                )
                
                log_text = (f"#pizza_sent\n\n"
                           f"Пользователь: {user_id} (@{user.get('username', 'N/A')})\n"
                           f"Адрес: {text}\n"
                           f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                           f"Отправлено пицц: {pizzas_sent}")
                
                await send_log_message(context, log_text)
                
                await send_main_menu(update, context, text="*🍕 Главное меню*")
            else:
                await update.message.reply_text(
                    "❌ *Ошибка!* Используйте ссылку `https://t.me`",
                    parse_mode="Markdown"
                )
            del context.user_data['awaiting_address']
        
        elif 'admin_action' in context.user_data:
            if user_id not in ADMIN_IDS:
                del context.user_data['admin_action']
                await send_main_menu(update, context)
                return
                
            action = context.user_data['admin_action']
            
            if action == 'take_sub_full':
                try:
                    target_id = int(text.strip())
                    target_user = get_user(target_id)
                    if target_user:
                        target_user["subscription"] = 0
                        update_user(target_id, target_user)
                        
                        await update.message.reply_text(
                            f"✅ *Подписка полностью изъята у пользователя {target_id}!*",
                            parse_mode="Markdown"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=target_id,
                                text="⚠️ *Ваша подписка была полностью изъята администратором!*",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось уведомить пользователя {target_id}: {e}")
                        
                        log_text = (f"#admin_action #take_sub_full\n\n"
                                   f"Админ: {user_id}\n"
                                   f"Пользователь: {target_id}")
                        
                        await send_log_message(context, log_text)
                    else:
                        await update.message.reply_text("❌ Пользователь не найден!")
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверный формат! Введите только ID пользователя."
                    )
            
            elif action == 'take_sub_date':
                try:
                    parts = text.split()
                    if len(parts) != 2:
                        raise ValueError
                    
                    target_id = int(parts[0])
                    date_str = parts[1]
                    
                    try:
                        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                    except ValueError:
                        await update.message.reply_text(
                            "❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ"
                        )
                        return
                    
                    target_user = get_user(target_id)
                    if target_user:
                        new_sub = min(
                            datetime.now().timestamp() if target_user["subscription"] < datetime.now().timestamp() else target_user["subscription"],
                            date_obj.timestamp()
                        )
                        
                        target_user["subscription"] = new_sub
                        update_user(target_id, target_user)
                        
                        await update.message.reply_text(
                            f"✅ *Подписка пользователя {target_id} установлена до {date_str}!*",
                            parse_mode="Markdown"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=target_id,
                                text=f"⚠️ *Ваша подписка была изменена администратором!*\n\n"
                                     f"Теперь она действует до {date_str}",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось уведомить пользователя {target_id}: {e}")
                        
                        log_text = (f"#admin_action #take_sub_date\n\n"
                                   f"Админ: {user_id}\n"
                                   f"Пользователь: {target_id}\n"
                                   f"Новая дата подписки: {date_str}")
                        
                        await send_log_message(context, log_text)
                    else:
                        await update.message.reply_text("❌ Пользователь не найден!")
                except:
                    await update.message.reply_text(
                        "❌ Неверный формат! Пример: `123456789 31.12.2023`",
                        parse_mode="Markdown"
                    )
            
            elif action == 'give_sub':
                try:
                    target_id, days = map(int, text.split())
                    target_user = get_user(target_id) or {
                        "username": "",
                        "status": "👤 Пользователь",
                        "subscription": 0,
                        "banned": False,
                        "subscribed": False,
                        "last_pizza_time": "",
                        "pizza_count": 0,
                        "read_manual": False
                    }
                    
                    if days == 36500:
                        new_sub = datetime.now().timestamp() + (36500 * 86400)
                    else:
                        if target_user["subscription"] > datetime.now().timestamp():
                            new_sub = target_user["subscription"] + (days * 86400)
                        else:
                            new_sub = datetime.now().timestamp() + (days * 86400)
                    
                    target_user["subscription"] = new_sub
                    update_user(target_id, target_user)
                    
                    await update.message.reply_text(
                        f"✅ *Подписка выдана!*\n"
                        f"Пользователь {target_id} получил +{days} дней.\n"
                        f"Теперь подписка действует до {datetime.fromtimestamp(target_user['subscription']).strftime('%d.%m.%Y %H:%M')}",
                        parse_mode="Markdown"
                    )
                    
                    try:
                        await context.bot.send_message(
                            chat_id=target_id,
                            text=f"🎉 *Вам выдана подписку на {days} дней!*\n\n"
                                 f"Теперь вы можете отправлять пиццу до {datetime.fromtimestamp(target_user['subscription']).strftime('%d.%m.%Y %H:%M')}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить пользователя {target_id}: {e}")
                    
                    log_text = (f"#admin_action #give_sub\n\n"
                               f"Админ: {user_id}\n"
                               f"Пользователь: {target_id}\n"
                               f"Дней: {days}\n"
                               f"Новая подписка до: {datetime.fromtimestamp(new_sub).strftime('%d.%m.%Y %H:%M')}")
                    
                    await send_log_message(context, log_text)
                    
                except:
                    await update.message.reply_text(
                        "❌ Неверный формат! Пример: `123456789 30`",
                        parse_mode="Markdown"
                    )
            
            elif action == 'ban_user':
                try:
                    target_id = int(text.strip())
                    if target_id == user_id:
                        await update.message.reply_text("❌ Нельзя заблокировать самого себя!")
                        return

                    target_user = get_user(target_id)
                    if not target_user:
                        await update.message.reply_text(f"❌ Пользователь с ID {target_id} не найден!")
                        return

                    target_user["banned"] = True
                    update_user(target_id, target_user)

                    await update.message.reply_text(
                        f"✅ Пользователь {target_id} успешно заблокирован!\n"
                        f"Теперь он не сможет использовать бота."
                    )

                    try:
                        await context.bot.send_message(
                            chat_id=target_id,
                            text="⛔ *Вы были заблокированы в этом боте!*\n\n"
                                 "Если вы считаете это ошибкой, свяжитесь с администратором.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить пользователя {target_id} о блокировке: {e}")

                    log_text = (f"#admin_action #ban\n\n"
                               f"Админ: {user_id}\n"
                               f"Заблокирован: {target_id}")
                    
                    await send_log_message(context, log_text)

                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверный формат ID! Введите только цифры."
                    )
                except Exception as e:
                    logger.error(f"Ошибка при блокировке пользователя: {e}")
                    await update.message.reply_text(
                        "❌ Произошла ошибка при блокировке пользователя. Подробности в логах."
                    )
            
            elif action == 'unban_user':
                try:
                    target_id = int(text.strip())
                    target_user = get_user(target_id)
                    if target_user:
                        target_user["banned"] = False
                        update_user(target_id, target_user)
                        await update.message.reply_text(
                            f"✅ Пользователь {target_id} успешно разблокирован!"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=target_id,
                                text="🎉 *Вы были разблокированы в этом боте!*\n\n"
                                     "Теперь вы снова можете использовать все функции бота.",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось уведомить пользователя {target_id} о разблокировке: {e}")
                        
                        log_text = (f"#admin_action #unban\n\n"
                                   f"Админ: {user_id}\n"
                                   f"Разблокирован: {target_id}")
                        
                        await send_log_message(context, log_text)
                    else:
                        await update.message.reply_text("❌ Пользователь не найден!")
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверный формат ID! Введите только цифры."
                    )
                except Exception as e:
                    logger.error(f"Ошибка при разблокировке пользователя: {e}")
                    await update.message.reply_text(
                        "❌ Произошла ошибка при разблокировке пользователя. Подробности в логах."
                    )
            
            elif action == 'broadcast':
                users_list = get_all_users()
                success = 0
                failed = 0
                
                msg = await update.message.reply_text(
                    f"*📢 Начата рассылка сообщения...*\n"
                    f"Получателей: {len(users_list)}",
                    parse_mode="Markdown"
                )
                
                for uid in users_list:
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=text,
                            parse_mode=None,
                            disable_web_page_preview=True
                        )
                        success += 1
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения {uid}: {e}")
                        failed += 1
                    
                    if success % 10 == 0:
                        await msg.edit_text(
                            f"*📢 Рассылка сообщения...*\n"
                            f"Успешно: {success}\n"
                            f"Не удалось: {failed}",
                            parse_mode="Markdown"
                        )
                
                await msg.edit_text(
                    f"*✅ Рассылка завершена!*\n"
                    f"Успешно: {success}\n"
                    f"Не удалось: {failed}",
                    parse_mode="Markdown"
                )
                
                log_text = (f"#admin_action #broadcast\n\n"
                           f"Админ: {user_id}\n"
                           f"Сообщение: {text[:100]}...\n"
                           f"Успешно: {success}\n"
                           f"Не удалось: {failed}")
                
                await send_log_message(context, log_text)
            
            elif action == 'create_promo':
                try:
                    parts = text.split()
                    if len(parts) < 3:
                        raise ValueError
                    
                    code = parts[0]
                    days = int(parts[1])
                    max_activations = int(parts[2])
                    description = " ".join(parts[3:]) if len(parts) > 3 else ""
                    
                    if create_promo_code(code, days, max_activations, user_id, description):
                        await update.message.reply_text(
                            f"✅ *Промокод создан!*\n\n"
                            f"Код: `{code}`\n"
                            f"Дней: {days}\n"
                            f"Макс. активаций: {max_activations}\n"
                            f"Описание: {description}",
                            parse_mode="Markdown"
                        )
                        
                        log_text = (f"#admin_action #promo_created\n\n"
                                   f"Админ: {user_id}\n"
                                   f"Промокод: {code}\n"
                                   f"Дней: {days}\n"
                                   f"Макс. активаций: {max_activations}\n"
                                   f"Описание: {description}")
                        
                        await send_log_message(context, log_text)
                    else:
                        await update.message.reply_text(
                            "❌ *Ошибка!* Такой промокод уже существует.",
                            parse_mode="Markdown"
                        )
                except:
                    await update.message.reply_text(
                        "❌ Неверный формат! Пример: `SUMMER2023 30 10 Летняя акция`",
                        parse_mode="Markdown"
                    )
            
            del context.user_data['admin_action']
            await send_main_menu(update, context)
        
        elif 'awaiting_promo' in context.user_data:
            code = text.strip()
            success, message = activate_promo_code(user_id, code)
            
            if success:
                promo_info = get_promo_code(code)
                log_text = (f"#promo_activated\n\n"
                           f"Пользователь: {user_id} (@{user.get('username', 'N/A')})\n"
                           f"Промокод: {code}\n"
                           f"Дней: {promo_info['days'] if promo_info else 'N/A'}\n"
                           f"Описание: {promo_info.get('description', 'N/A') if promo_info else 'N/A'}")
                
                await send_log_message(context, log_text)
            
            await update.message.reply_text(
                f"ℹ️ {message}",
                parse_mode="Markdown"
            )
            del context.user_data['awaiting_promo']
            await send_main_menu(update, context)
        
        elif 'awaiting_name_update' in context.user_data:
            user_full_name = update.effective_user.full_name or ""
            if REQUIRED_NAME.lower() not in user_full_name.lower():
                keyboard = [
                    [InlineKeyboardButton("🔙 Профиль", callback_data='profile')]
                ]
                await update.message.reply_text(
                    text=f"❌ *Вы не добавили {REQUIRED_NAME} в ник!*\n\n"
                         f"Добавьте в свой ник это, чтобы продолжить.\n"
                         f"*Пример: Venom @Logunovv_delivery_bot*\n\n"
                         f"После изменения попробуйте ещё раз!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                return
            
            keyboard = [[InlineKeyboardButton("🔙 Профиль", callback_data='profile')]]
            await update.message.reply_text(
                text="*🎁 Активация промокода*\n\n"
                     "Введите промокод:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data['awaiting_promo'] = True
            del context.user_data['awaiting_name_update']
        
        else:
            # Проверяем подписку при каждом сообщении
            subscribed = await check_all_subscriptions(context, user_id)
            if not subscribed:
                await ask_for_subscriptions(update, context)
                return
            
            await send_main_menu(update, context)

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await send_main_menu(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and isinstance(update, Update) and update.effective_user:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="⚠️ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
        )

def main() -> None:
    application = Application.builder().token("8499345141:AAE-F5VSbDy3ToCXul6cFAg9HN2u-nb0sCs").build()

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()