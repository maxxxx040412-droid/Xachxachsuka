import json
import logging
import sqlite3
import urllib.parse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    Message,
    WebAppInfo,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

TOKEN = "ТОКЕН_ТВОЕГО_БОТА"  # <--- Вставь сюда токен своего бота от @BotFather
ADMIN_ID = 123456789         # <--- Вставь сюда свой Telegram ID
WEBAPP_URL = "https://maxxxx040412-droid.github.io/Xachxachsuka/"

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
            balance INTEGER DEFAULT 10000
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_title TEXT,
            price INTEGER
        )
    """)
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


def get_or_create_player(user_id: int, username: str) -> int:
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        default_balance = 10000  # Старт: 10 000 шекелей для новых игроков
        cursor.execute(
            "INSERT INTO players (user_id, username, balance) VALUES (?, ?, ?)",
            (user_id, username, default_balance),
        )
        conn.commit()
        balance = default_balance
    else:
        balance = row[0]
    conn.close()
    return balance


def update_player_balance(user_id: int, amount: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE players SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def add_to_inventory(user_id: int, item_title: str, price: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO inventory (user_id, item_title, price) VALUES (?, ?, ?)",
        (user_id, item_title, price),
    )
    conn.commit()
    conn.close()


def remove_one_from_inventory(user_id: int, item_title: str) -> bool:
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM inventory WHERE user_id = ? AND item_title = ? LIMIT 1",
        (user_id, item_title),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    cursor.execute("DELETE FROM inventory WHERE id = ?", (row[0],))
    conn.commit()
    conn.close()
    return True


def get_player_inventory(user_id: int):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_title, price FROM inventory WHERE user_id = ?", (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_active_ads():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, item_title, price FROM marketplace_ads WHERE status = 'active' ORDER BY id DESC LIMIT 15"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- ГЕНЕРАЦИЯ КЛАВИАТУРЫ С ПЕРЕДАЧЕЙ ДАННЫХ В WEBAPP ---
def get_main_keyboard(user_id: int, username: str) -> ReplyKeyboardMarkup:
    balance = get_or_create_player(user_id, username)
    inv = [item[0] for item in get_player_inventory(user_id)]
    ads = [
        {"id": r[0], "seller": r[1], "item": r[2], "price": r[3]}
        for r in get_active_ads()
    ]

    params = urllib.parse.urlencode({
        "bal": balance,
        "inv": json.dumps(inv, ensure_ascii=False),
        "ads": json.dumps(ads, ensure_ascii=False),
    })
    full_url = f"{WEBAPP_URL}?{params}"

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛵 Открыть Scooter Market",
                    web_app=WebAppInfo(url=full_url),
                )
            ],
            [KeyboardButton(text="👤 Профиль и гараж")],
        ],
        resize_keyboard=True,
    )


# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    await message.answer(
        f"Здарова, {user.first_name}! 🤝\n"
        f"💰 Твой стартовый баланс: **{balance:,} шекелей**\n\n"
        "Жми кнопку **«🛵 Открыть Scooter Market»** внизу экрана, чтобы зайти в игру, посмотреть свой гараж и доску объявлений!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user.id, user.first_name),
    )


@dp.message(Command("profile"))
@dp.message(F.text == "👤 Профиль и гараж")
async def cmd_profile(message: Message):
    user = message.from_user
    balance = get_or_create_player(user.id, user.first_name)
    inventory = get_player_inventory(user.id)

    inv_text = (
        "\n".join([f"• {item[0]} ({item[1]:,} шекелей)" for item in inventory])
        if inventory
        else "Пусто (гараж пуст)"
    )

    await message.answer(
        f"👤 **Профиль перекупа:** {user.first_name}\n"
        f"💵 Баланс: **{balance:,} шекелей**\n\n"
        f"🎒 **Твой гараж:**\n{inv_text}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user.id, user.first_name),
    )


# --- ОБРАБОТКА ДЕЙСТВИЙ ИЗ WEB APP ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    user = message.from_user
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        # 1. Покупка в официальном магазине
        if action == "buy_game_item":
            item_title = data.get("item")
            price = int(data.get("price"))
            current_balance = get_or_create_player(user.id, user.first_name)

            if current_balance < price:
                await message.answer(
                    f"⚠️ Недостаточно шекелей! Нужно {price:,}, у тебя {current_balance:,}.",
                    reply_markup=get_main_keyboard(user.id, user.first_name),
                )
                return

            update_player_balance(user.id, -price)
            add_to_inventory(user.id, item_title, price)
            new_balance = get_or_create_player(user.id, user.first_name)

            await message.answer(
                f"🎉 **Сделка успешна!**\n"
                f"🛵 Куплено: **{item_title}**\n"
                f"💸 Списано: {price:,} шекелей\n"
                f"💰 Баланс: **{new_balance:,} шекелей**",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user.id, user.first_name),
            )

        # 2. Выставление лота на модерацию
        elif action == "sell_ad":
            item_title = data.get("item")
            price = int(data.get("price"))

            if price <= 0:
                await message.answer("⚠️ Укажи корректную цену!")
                return

            if not remove_one_from_inventory(user.id, item_title):
                await message.answer(
                    f"⚠️ У тебя в гараже нет аппарата «{item_title}»!",
                    reply_markup=get_main_keyboard(user.id, user.first_name),
                )
                return

            conn = sqlite3.connect("game.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO marketplace_ads (user_id, username, item_title, price, status) VALUES (?, ?, ?, ?, 'pending')",
                (user.id, user.first_name, item_title, price),
            )
            ad_id = cursor.lastrowid
            conn.commit()
            conn.close()

            await message.answer(
                f"⏳ Заявка на продажу **{item_title}** за **{price:,} шекелей** улетела админу на проверку!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user.id, user.first_name),
            )

            admin_kb = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Выставить", callback_data=f"ad_yes_{ad_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить", callback_data=f"ad_no_{ad_id}"
                    ),
                ]]
            )
            await bot.send_message(
                ADMIN_ID,
                f"📢 **Новое объявление на модерацию!**\n\n"
                f"👤 Продавец: {user.first_name} (`{user.id}`)\n"
                f"🛵 Лот: **{item_title}**\n"
                f"💵 Цена: **{price:,} шекелей**",
                parse_mode="Markdown",
                reply_markup=admin_kb,
            )

        # 3. Покупка чужого лота с доски объявлений
        elif action == "buy_user_ad":
            ad_id = int(data.get("ad_id"))
            conn = sqlite3.connect("game.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, item_title, price, status FROM marketplace_ads WHERE id = ?",
                (ad_id,),
            )
            ad = cursor.fetchone()

            if not ad or ad[4] != "active":
                conn.close()
                await message.answer(
                    "⚠️ Этот лот уже купили или сняли с продажи.",
                    reply_markup=get_main_keyboard(user.id, user.first_name),
                )
                return

            seller_id, seller_name, item_title, price, _ = ad
            if seller_id == user.id:
                conn.close()
                await message.answer(
                    "⚠️ Свой собственный лот купить нельзя!",
                    reply_markup=get_main_keyboard(user.id, user.first_name),
                )
                return

            buyer_balance = get_or_create_player(user.id, user.first_name)
            if buyer_balance < price:
                conn.close()
                await message.answer(
                    f"⚠️ Не хватает шекелей! Нужно {price:,}, у тебя {buyer_balance:,}.",
                    reply_markup=get_main_keyboard(user.id, user.first_name),
                )
                return

            cursor.execute(
                "UPDATE marketplace_ads SET status = 'sold' WHERE id = ?", (ad_id,)
            )
            conn.commit()
            conn.close()

            update_player_balance(user.id, -price)
            update_player_balance(seller_id, price)
            add_to_inventory(user.id, item_title, price)

            await message.answer(
                f"🤝 **Сделка успешно завершена!**\n"
                f"Ты купил **{item_title}** у игрока {seller_name} за **{price:,} шекелей**!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user.id, user.first_name),
            )
            try:
                await bot.send_message(
                    seller_id,
                    f"💸 **Твой самокат купили!**\n"
                    f"Игрок {user.first_name} приобрел **{item_title}** за **{price:,} шекелей**!",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(seller_id, seller_name),
                )
            except Exception:
                pass

    except Exception as e:
        logging.error(f"Ошибка WebApp: {e}")
        await message.answer("⚠️ Ошибка обработки действия.")


# --- МОДЕРАЦИЯ АДМИНОМ ---
@dp.callback_query(F.data.startswith("ad_"))
async def moderate_ad(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ Только для главного админа!", show_alert=True)
        return

    _, decision, ad_id_str = callback.data.split("_")
    ad_id = int(ad_id_str)

    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, item_title, price, status FROM marketplace_ads WHERE id = ?",
        (ad_id,),
    )
    ad = cursor.fetchone()

    if not ad or ad[4] != "pending":
        conn.close()
        await callback.message.edit_text("⚠️ Заявка уже была рассмотрена ранее.")
        return

    seller_id, seller_name, item_title, price, _ = ad

    if decision == "yes":
        cursor.execute(
            "UPDATE marketplace_ads SET status = 'active' WHERE id = ?", (ad_id,)
        )
        conn.commit()
        conn.close()
        await callback.message.edit_text(
            f"✅ Лот **{item_title}** за {price:,} шекелей (от {seller_name}) успешно одобрен и выставлен!",
            parse_mode="Markdown",
        )
        try:
            await bot.send_message(
                seller_id,
                f"✅ Твое объявление о продаже **{item_title}** прошло модерацию и опубликовано на доске!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(seller_id, seller_name),
            )
        except Exception:
            pass
    else:
        cursor.execute(
            "UPDATE marketplace_ads SET status = 'rejected' WHERE id = ?", (ad_id,)
        )
        conn.commit()
        conn.close()
        # Возвращаем самокат продавцу в инвентарь
        add_to_inventory(seller_id, item_title, price)
        await callback.message.edit_text(
            f"❌ Лот **{item_title}** от {seller_name} отклонен. Самокат возвращен в гараж.",
            parse_mode="Markdown",
        )
        try:
            await bot.send_message(
                seller_id,
                f"❌ Админ отклонил объявление на **{item_title}**. Транспорт возвращен тебе в гараж.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(seller_id, seller_name),
            )
        except Exception:
            pass

    await callback.answer()


# --- ЗАПУСК БОТА ---
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Бот успешно запущен и ждет игроков...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
