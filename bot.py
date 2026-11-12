import json
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
ADMIN_ID = 123456789  # <--- ЗАМЕНИ НА СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    # Таблица игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1500000
        )
    """)
    # Таблица инвентаря (купленные самокаты)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_title TEXT,
            price INTEGER
        )
    """)
    # Таблица объявлений на модерацию (доска объявлений)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marketplace_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            item_title TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def get_or_create_player(user_id: int, username: str):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        default_balance = 1500000
        cursor.execute("INSERT INTO players (user_id, username, balance) VALUES (?, ?, ?)", 
                       (user_id, username, default_balance))
        conn.commit()
        balance = default_balance
    else:
        balance = row[0]
    conn.close()
    return balance

def update_player_balance(user_id: int, amount: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def add_to_inventory(user_id: int, item_title: str, price: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory (user_id, item_title, price) VALUES (?, ?, ?)", (user_id, item_title, price))
    conn.commit()
    conn.close()

def get_player_inventory(user_id: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item_title, price FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- КЛАВИАТУРА ---
def get_market_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛵 Открыть Scooter Market",
                    web_app=WebAppInfo(url="https://maxxxx040412-droid.github.io/Xachxachsuka/")
                )
            ]
        ]
    )


# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    await message.answer(
        f"Здарова, {user.first_name}! 🤝\n"
        "Добро пожаловать в игру «Хач перекуп самокатов».\n\n"
        f"💰 Твой баланс: **{balance:,} шекелей**\n\n"
        "Залетай в маркетплейс, выбирай аппараты и забирай лимитки!",
        parse_mode="Markdown",
        reply_markup=get_market_keyboard()
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    inventory = get_player_inventory(user.id)
    
    inv_text = "\n".join([f"• {item[0]} ({item[1]:,} шекелей)" for item in inventory]) if inventory else "Пусто (пока ничего не купил)"
    
    await message.answer(
        f"👤 **Твой профиль перекупа:**\n\n"
        f"Имя: {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"💵 Баланс: **{balance:,} шекелей**\n\n"
        f"🎒 **Твой инвентарь:**\n{inv_text}",
        parse_mode="Markdown",
        reply_markup=get_market_keyboard()
    )


# --- ПОКУПКА ТОВАРА ИЗ WEB APP ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    user = message.from_user
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        
        if action == "buy_game_item":
            item_title = data.get("item")
            price = data.get("price")
            current_balance = get_or_create_player(user.id, user.first_name)
            
            if current_balance < price:
                await message.answer(
                    f"⚠️ **Недостаточно шекелей!**\n"
                    f"Нужно: {price:,} | У тебя: {current_balance:,}",
                    parse_mode="Markdown"
                )
                return
            
            # Списываем баланс, добавляем в инвентарь
            update_player_balance(user.id, -price)
            add_to_inventory(user.id, item_title, price)
            new_balance = get_or_create_player(user.id, user.first_name)
            
            await message.answer(
                f"🎉 **Сделка века оформлена!**\n\n"
                f"🛵 Транспорт: **{item_title}** зачислен в инвентарь!\n"
                f"💰 Остаток: **{new_balance:,} шекелей**\n\n"
                f"Проверить инвентарь: /profile",
                parse_mode="Markdown",
                reply_markup=get_market_keyboard()
            )
            
        elif action == "sell_ad":
            # Игрок хочет выставить объявление на доску
            item_title = data.get("item")
            price = data.get("price")
            
            conn = sqlite3.connect("game.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO marketplace_ads (user_id, username, item_title, price) VALUES (?, ?, ?, ?)",
                           (user.id, user.first_name, item_title, price))
            ad_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            await message.answer("📝 Твое объявление отправлено на модерацию главному перекупу (админу)!")
            
            # Шлем заявку тебе в ЛС с кнопками
            admin_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Выставить", callback_data=f"ad_yes_{ad_id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ad_no_{ad_id}")
                    ]
                ]
            )
            await bot.send_message(
                ADMIN_ID,
                f"📢 **Новое объявление на доску!**\n\n"
                f"👤 Продавец: {user.first_name} (ID: `{user.id}`)\n"
                f"🛵 Лот: **{item_title}**\n"
                f"💵 Цена: **{price:,} шекелей**",
                parse_mode="Markdown",
                reply_markup=admin_kb
            )

    except Exception as e:
        logging.error(f"Ошибка обработки Web App: {e}")
        await message.answer("⚠️ Ошибка обработки транзакции.")


# --- МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ АДМИНОМ ---
@dp.callback_query(F.data.startswith("ad_"))
async def moderate_ad(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ Только для админа!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    action = parts[1]
    ad_id = int(parts[2])
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, item_title, price FROM marketplace_ads WHERE id = ?", (ad_id,))
    ad = cursor.fetchone()
    
    if not ad:
        await callback.message.edit_text("⚠️ Объявление уже обработано или не найдено.")
        conn.close()
        return
    
    seller_id, item_title, price = ad
    
    if action == "yes":
        cursor.execute("UPDATE marketplace_ads SET status = 'active' WHERE id = ?", (ad_id,))
        conn.commit()
        await callback.message.edit_text(f"✅ Объявление от ID `{seller_id}` (**{item_title}** за {price:,}) одобрено и выставлено!", parse_mode="Markdown")
        try:
            await bot.send_message(seller_id, f"🎉 Твое объявление «{item_title}» успешно прошло модерацию и выставлено на рынок!")
        except:
            pass
    else:
        cursor.execute("UPDATE marketplace_ads SET status = 'rejected' WHERE id = ?", (ad_id,))
        conn.commit()
        await callback.message.edit_text(f"❌ Объявление от ID `{seller_id}` отклонено.")
        try:
            await bot.send_message(seller_id, f"⚠️ Твое объявление «{item_title}» было отклонено админом.")
        except:
            pass
            
    conn.close()
    await callback.answer()


@asyncio.run if __name__ == "__main__" else None # (Запуск стандартный)
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Бот с инвентарем и модерацией запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())import json
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
ADMIN_ID = 123456789  # <--- ЗАМЕНИ НА СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    # Таблица игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1500000
        )
    """)
    # Таблица инвентаря (купленные самокаты)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_title TEXT,
            price INTEGER
        )
    """)
    # Таблица объявлений на модерацию (доска объявлений)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marketplace_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            item_title TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def get_or_create_player(user_id: int, username: str):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        default_balance = 1500000
        cursor.execute("INSERT INTO players (user_id, username, balance) VALUES (?, ?, ?)", 
                       (user_id, username, default_balance))
        conn.commit()
        balance = default_balance
    else:
        balance = row[0]
    conn.close()
    return balance

def update_player_balance(user_id: int, amount: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def add_to_inventory(user_id: int, item_title: str, price: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory (user_id, item_title, price) VALUES (?, ?, ?)", (user_id, item_title, price))
    conn.commit()
    conn.close()

def get_player_inventory(user_id: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item_title, price FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- КЛАВИАТУРА ---
def get_market_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛵 Открыть Scooter Market",
                    web_app=WebAppInfo(url="https://maxxxx040412-droid.github.io/Xachxachsuka/")
                )
            ]
        ]
    )


# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    await message.answer(
        f"Здарова, {user.first_name}! 🤝\n"
        "Добро пожаловать в игру «Хач перекуп самокатов».\n\n"
        f"💰 Твой баланс: **{balance:,} шекелей**\n\n"
        "Залетай в маркетплейс, выбирай аппараты и забирай лимитки!",
        parse_mode="Markdown",
        reply_markup=get_market_keyboard()
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    inventory = get_player_inventory(user.id)
    
    inv_text = "\n".join([f"• {item[0]} ({item[1]:,} шекелей)" for item in inventory]) if inventory else "Пусто (пока ничего не купил)"
    
    await message.answer(
        f"👤 **Твой профиль перекупа:**\n\n"
        f"Имя: {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"💵 Баланс: **{balance:,} шекелей**\n\n"
        f"🎒 **Твой инвентарь:**\n{inv_text}",
        parse_mode="Markdown",
        reply_markup=get_market_keyboard()
    )


# --- ПОКУПКА ТОВАРА ИЗ WEB APP ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    user = message.from_user
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        
        if action == "buy_game_item":
            item_title = data.get("item")
            price = data.get("price")
            current_balance = get_or_create_player(user.id, user.first_name)
            
            if current_balance < price:
                await message.answer(
                    f"⚠️ **Недостаточно шекелей!**\n"
                    f"Нужно: {price:,} | У тебя: {current_balance:,}",
                    parse_mode="Markdown"
                )
                return
            
            # Списываем баланс, добавляем в инвентарь
            update_player_balance(user.id, -price)
            add_to_inventory(user.id, item_title, price)
            new_balance = get_or_create_player(user.id, user.first_name)
            
            await message.answer(
                f"🎉 **Сделка века оформлена!**\n\n"
                f"🛵 Транспорт: **{item_title}** зачислен в инвентарь!\n"
                f"💰 Остаток: **{new_balance:,} шекелей**\n\n"
                f"Проверить инвентарь: /profile",
                parse_mode="Markdown",
                reply_markup=get_market_keyboard()
            )
            
        elif action == "sell_ad":
            # Игрок хочет выставить объявление на доску
            item_title = data.get("item")
            price = data.get("price")
            
            conn = sqlite3.connect("game.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO marketplace_ads (user_id, username, item_title, price) VALUES (?, ?, ?, ?)",
                           (user.id, user.first_name, item_title, price))
            ad_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            await message.answer("📝 Твое объявление отправлено на модерацию главному перекупу (админу)!")
            
            # Шлем заявку тебе в ЛС с кнопками
            admin_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Выставить", callback_data=f"ad_yes_{ad_id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ad_no_{ad_id}")
                    ]
                ]
            )
            await bot.send_message(
                ADMIN_ID,
                f"📢 **Новое объявление на доску!**\n\n"
                f"👤 Продавец: {user.first_name} (ID: `{user.id}`)\n"
                f"🛵 Лот: **{item_title}**\n"
                f"💵 Цена: **{price:,} шекелей**",
                parse_mode="Markdown",
                reply_markup=admin_kb
            )

    except Exception as e:
        logging.error(f"Ошибка обработки Web App: {e}")
        await message.answer("⚠️ Ошибка обработки транзакции.")


# --- МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ АДМИНОМ ---
@dp.callback_query(F.data.startswith("ad_"))
async def moderate_ad(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ Только для админа!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    action = parts[1]
    ad_id = int(parts[2])
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, item_title, price FROM marketplace_ads WHERE id = ?", (ad_id,))
    ad = cursor.fetchone()
    
    if not ad:
        await callback.message.edit_text("⚠️ Объявление уже обработано или не найдено.")
        conn.close()
        return
    
    seller_id, item_title, price = ad
    
    if action == "yes":
        cursor.execute("UPDATE marketplace_ads SET status = 'active' WHERE id = ?", (ad_id,))
        conn.commit()
        await callback.message.edit_text(f"✅ Объявление от ID `{seller_id}` (**{item_title}** за {price:,}) одобрено и выставлено!", parse_mode="Markdown")
        try:
            await bot.send_message(seller_id, f"🎉 Твое объявление «{item_title}» успешно прошло модерацию и выставлено на рынок!")
        except:
            pass
    else:
        cursor.execute("UPDATE marketplace_ads SET status = 'rejected' WHERE id = ?", (ad_id,))
        conn.commit()
        await callback.message.edit_text(f"❌ Объявление от ID `{seller_id}` отклонено.")
        try:
            await bot.send_message(seller_id, f"⚠️ Твое объявление «{item_title}» было отклонено админом.")
        except:
            pass
            
    conn.close()
    await callback.answer()


@asyncio.run if __name__ == "__main__" else None # (Запуск стандартный)
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Бот с инвентарем и модерацией запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
