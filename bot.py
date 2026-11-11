import asyncio
import aiosqlite
from aiogram import F, types, Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Твой реальный Telegram ID для админ-панели
ADMIN_ID = 5250617443  

# Вставь сюда токен твоего бота, полученный от BotFather
TOKEN = "912096033:AAHg-JbERYt79LY69pxNjTaKMmIYNoCexo"  [cite: 13]

bot = Bot(token=TOKEN)
dp = Dispatcher()

MAX_SCOOTERS = 50

class SellScooter(StatesGroup):
    title = State()
    price = State()
    description = State()
    city = State()
    photo = State()

class AdminGiveLimit(StatesGroup):
    user_id = State()
    title = State()
    price = State()
    description = State()
    city = State()
    photo = State()


# Инициализация базы данных (со стартовым балансом 10 000 шекелей)
async def init_db():
    async with aiosqlite.connect("scooter_bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 10000,
                username TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                price INTEGER,
                description TEXT,
                city TEXT,
                rarity TEXT DEFAULT 'Обычный',
                photo_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def count_ads() -> int:
    async with aiosqlite.connect("scooter_bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM ads") as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0


# Старт и регистрация игрока (10 000 шекелей)
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    async with aiosqlite.connect("scooter_bot.db") as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, balance, username) VALUES (?, ?, ?)",
                (user_id, 10000, username)
            )
            await db.commit()
            await message.answer("👋 Добро пожаловать в игру!\n🎁 Твой стартовый капитал: **10 000 шекелей** ₪", parse_mode="Markdown")
        else:
            await message.answer("С возвращением в игру! 🛴")


@dp.message(F.text == "➕ Продать самокат")
async def sell_start(message: types.Message, state: FSMContext):
    count = await count_ads()
    if count >= MAX_SCOOTERS:
        await message.answer(f"🚫 Лимит объявлений исчерпан ({MAX_SCOOTERS}/{MAX_SCOOTERS}).")
        return
    
    await state.set_state(SellScooter.title)
    await message.answer("📝 Напиши название самоката (или лимитки):")


@dp.message(SellScooter.title)
async def sell_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(SellScooter.price)
    await message.answer("💰 Укажи цену в шекелях (только число):")


@dp.message(SellScooter.price)
async def sell_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Нужно ввести только положительное число:")
        return
    
    price = int(message.text)
    if price <= 0:
        await message.answer("⚠️ Цена должна быть больше нуля:")
        return

    await state.update_data(price=price)
    await state.set_state(SellScooter.description)
    await message.answer("📄 Напиши описание (состояние, пробег и т.д.):")


@dp.message(SellScooter.description)
async def sell_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(SellScooter.city)
    await message.answer("📍 В каком городе находится транспорт?")


@dp.message(SellScooter.city)
async def sell_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(SellScooter.photo)
    await message.answer("📸 Пришли <b>фото</b> (обязательно):", parse_mode="HTML")


@dp.message(SellScooter.photo, F.photo)
async def sell_photo(message: types.Message, state: FSMContext):
    count = await count_ads()
    if count >= MAX_SCOOTERS:
        await message.answer(f"🚫 Лимит объявлений исчерпан ({MAX_SCOOTERS}/{MAX_SCOOTERS}).")
        await state.clear()
        return

    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    title_lower = data["title"].lower()

    # Автоматическое определение игровых лимиток по названию
    rarity = "Обычный"
    if "ланцетик" in title_lower:
        rarity = "⭐ Лимитка (Ланцетик)"
    elif "шахед" in title_lower:
        rarity = "⭐ Лимитка (757 шахед стент тим)"
    elif "г2" in title_lower or "царский г2" in title_lower:
        rarity = "👑 Экстра (Царский Г2)"
    elif "могг" in title_lower or "mogg4" in title_lower:
        rarity = "⭐ Лимитка (Kugoo MOGG4)"
    elif "пивной" in title_lower:
        rarity = "⭐ Лимитка (Пивной найинбот)"

    async with aiosqlite.connect("scooter_bot.db") as db:
        await db.execute(
            """INSERT INTO ads (user_id, title, price, description, city, rarity, photo_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message.from_user.id, data["title"], data["price"], data["description"],
             data["city"], rarity, photo_id)
        )
        await db.commit()

    await state.clear()
    formatted_price = f"{data['price']:,}".replace(",", " ")
    
    caption = (
        f"✅ <b>Объявление опубликовано!</b>\n\n"
        f"<b>{data['title']}</b>\n"
        f"🏷 {rarity}\n"
        f"💰 {formatted_price} ₪\n"
        f"📍 {data['city']}\n\n"
        f"{data['description']}"
    )
    await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML")


@dp.message(F.text == "📋 Смотреть объявления")
async def list_ads(message: types.Message):
    async with aiosqlite.connect("scooter_bot.db") as db:
        async with db.execute(
            "SELECT id, title, price, city, description, rarity, photo_id FROM ads ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("📭 Пока нет активных объявлений.")
        return

    for ad_id, title, price, city, desc, rarity, photo_id in rows:
        formatted_price = f"{price:,}".replace(",", " ")
        caption = (
            f"#{ad_id} | <b>{title}</b>\n"
            f"🏷 {rarity}\n"
            f"💰 {formatted_price} ₪\n"
            f"📍 {city}\n\n"
            f"{desc}"
        )
        
        if photo_id:
            await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")


# ==================== АДМИН-ПАНЕЛЬ (ТОЛЬКО ДЛЯ ТЕБЯ) ====================

@dp.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return  # Обычным игрокам вообще не показываем панель
    
    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        "Команды:\n"
        "• `/add_money <ID> <сумма>` — выдать шекели\n"
        "• `/give_limit` — выдать лимитку игроку лично\n"
        "• `/stats` — статистика игры",
        parse_mode="HTML"
    )

@dp.message(F.text.startswith("/add_money"))
async def admin_add_money(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Использование: `/add_money ID СУММА`", parse_mode="Markdown")
        return
    
    target_id = int(args[1])
    amount = int(args[2])

    async with aiosqlite.connect("scooter_bot.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        await db.commit()

    await message.answer(f"✅ Успешно добавлено {amount:,} ₪ игроку `{target_id}`!".replace(",", " "), parse_mode="Markdown")


# Выдача лимитки лично админом
@dp.message(F.text == "/give_limit")
async def admin_give_limit_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await state.set_state(AdminGiveLimit.user_id)
    await message.answer("👤 Введи Telegram ID игрока для выдачи лимитки:")

@dp.message(AdminGiveLimit.user_id)
async def admin_give_limit_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ ID должен состоять только из цифр:")
        return
    await state.update_data(target_user_id=int(message.text))
    await state.set_state(AdminGiveLimit.title)
    await message.answer("🏷 Название лимитки:")

@dp.message(AdminGiveLimit.title)
async def admin_give_limit_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminGiveLimit.price)
    await message.answer("💰 Цена в шекелях:")

@dp.message(AdminGiveLimit.price)
async def admin_give_limit_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введи число:")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AdminGiveLimit.description)
    await message.answer("📝 Описание лимитки:")

@dp.message(AdminGiveLimit.description)
async def admin_give_limit_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminGiveLimit.city)
    await message.answer("📍 Город:")

@dp.message(AdminGiveLimit.city)
async def admin_give_limit_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(AdminGiveLimit.photo)
    await message.answer("📸 Отправь фото лимитки:")

@dp.message(AdminGiveLimit.photo, F.photo)
async def admin_give_limit_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    target_id = data["target_user_id"]
    rarity = "👑 Эксклюзив от Админа"

    async with aiosqlite.connect("scooter_bot.db") as db:
        await db.execute(
            """INSERT INTO ads (user_id, title, price, description, city, rarity, photo_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (target_id, data["title"], data["price"], data["description"],
             data["city"], rarity, photo_id)
        )
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Лимитка **{data['title']}** успешно выдана игроку `{target_id}`!", parse_mode="Markdown")
    
    try:
        formatted_price = f"{data['price']:,}".replace(",", " ")
        caption = (
            f"🎁 <b>Вам выдана эксклюзивная лимитка!</b>\n\n"
            f"<b>{data['title']}</b>\n"
            f"🏷 {rarity}\n"
            f"💰 {formatted_price} ₪\n"
            f"📍 {data['city']}\n\n"
            f"{data['description']}"
        )
        await bot.send_photo(chat_id=target_id, photo=photo_id, caption=caption, parse_mode="HTML")
    except Exception:
        pass


@dp.message(F.text == "/stats")
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect("scooter_bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            users_count = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM ads") as c2:
            ads_count = (await c2.fetchone())[0]

    await message.answer(f"📊 <b>Статистика игры:</b>\n\n👥 Игроков: {users_count}\n🛴 Транспорта/Лимиток: {ads_count}", parse_mode="HTML")


async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
