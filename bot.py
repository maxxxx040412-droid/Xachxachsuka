import json
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Токен твоего Telegram-бота
TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
ADMIN_ID = 123456789  # <--- ЗАМЕНИ НА СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1500000
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
        default_balance = 1500000  # Стартовый капитал игрока
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

def reset_player_balance(user_id: int, new_balance: int = 1500000):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()


# --- КЛАВИАТУРА МЕНЮ ---
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
    
    welcome_text = (
        f"Здарова, {user.first_name}! 🤝\n"
        "Добро пожаловать в игру «Хач перекуп самокатов».\n\n"
        f"💰 Твой баланс: **{balance:,} шекелей**\n\n"
        "Залетай в маркетплейс, выбирай кастомные аппараты и забирай лимитки в инвентарь!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_market_keyboard())


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    
    await message.answer(
        f"👤 **Твой игровой профиль:**\n\n"
        f"Имя: {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"💵 Баланс: **{balance:,} шекелей**",
        parse_mode="Markdown",
        reply_markup=get_market_keyboard()
    )


# --- ПОКУПКА ЧЕРЕЗ WEB APP ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    user = message.from_user
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        item_title = data.get("item")
        price = data.get("price")
        
        if action == "buy_game_item":
            current_balance = get_or_create_player(user.id, user.first_name)
            
            # Защита от лазеек: проверка баланса на бэкенде
            if current_balance < price:
                await message.answer(
                    f"⚠️ **Недостаточно шекелей!**\n"
                    f"Стоимость: {price:,} | У тебя на балансе: {current_balance:,}",
                    parse_mode="Markdown"
                )
                return
            
            # Списываем средства
            update_player_balance(user.id, -price)
            new_balance = get_or_create_player(user.id, user.first_name)
            
            formatted_price = f"{price:,}".replace(",", " ")
            response_text = (
                f"🎉 **Сделка века оформлена!**\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🛵 Транспорт: **{item_title}**\n"
                f"💸 Списано: **{formatted_price} шекелей**\n"
                f"💰 Остаток на счете: **{new_balance:,} шекелей**"
            )
            await message.answer(response_text, parse_mode="Markdown", reply_markup=get_market_keyboard())
            
    except Exception as e:
        logging.error(f"Ошибка при покупке: {e}")
        await message.answer("⚠️ Ошибка обработки транзакции.")


# --- АДМИНСКАЯ КОМАНДА ДЛЯ ОБНУЛЕНИЯ ---
@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ Команда только для главного перекупа.\nЕсли нашел лазейку — чиркни админу в личку!")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: `/reset ID_игрока` (или `/reset me` для себя)", parse_mode="Markdown")
        return
    
    target = args[1]
    if target.lower() == "me":
        target_id = message.from_user.id
    else:
        try:
            target_id = int(target)
        except ValueError:
            await message.answer("Неверный ID игрока.")
            return

    reset_player_balance(target_id, 1500000)
    await message.answer(f"🔄 Баланс игрока с ID `{target_id}` успешно обнулен до 1 500 000 шекелей!", parse_mode="Markdown")


# --- ЗАПУСК ---
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Игровой бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
