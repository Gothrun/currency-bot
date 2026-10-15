import os
from dotenv import load_dotenv

load_dotenv()
import asyncio
import logging
import json
import os
import re
import difflib  # Встроенный модуль для поиска слов с опечатками!
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ----------------------------------------------------
# Настройки
# ----------------------------------------------------
TOKEN = os.getenv("BOT_TOKEN")

# ⚠️ ВСТАВЬ СЮДА СВОЙ TELEGRAM ID
ADMIN_ID = 962833829 

ALLOWED_FILE = "allowed_users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    waiting_for_add_id = State()
    waiting_for_remove_id = State()

def load_allowed_users() -> set:
    if os.path.exists(ALLOWED_FILE):
        try:
            with open(ALLOWED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_allowed_users(users_set: set):
    with open(ALLOWED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(users_set), f, ensure_ascii=False, indent=2)

allowed_users = load_allowed_users()

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📖 Инструкция"), KeyboardButton(text="👥 Список пользователей")],
        [KeyboardButton(text="➕ Добавить доступ"), KeyboardButton(text="➖ Закрыть доступ")]
    ],
    resize_keyboard=True
)

# Клавиатура для обычных пользователей (только кнопка инструкции)
user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📖 Инструкция")]
    ],
    resize_keyboard=True
)

# ----------------------------------------------------
# База знаний о валютах
# ----------------------------------------------------
CURRENCY_MAP = {
    # Доллар США
    'usd': 'USD', 'доллар': 'USD', 'долларах': 'USD', 'долларов': 'USD', 'доллара': 'USD', 'бакс': 'USD', 'баксов': 'USD', '$': 'USD',
    # Евро
    'eur': 'EUR', 'евро': 'EUR', '€': 'EUR',
    # Российский рубль
    'rub': 'RUB', 'рубль': 'RUB', 'рублях': 'RUB', 'рублей': 'RUB', 'рубля': 'RUB', 'руб': 'RUB', '₽': 'RUB',
    # Кыргызский сом
    'kgs': 'KGS', 'сом': 'KGS', 'сомах': 'KGS', 'сомов': 'KGS', 'сома': 'KGS', 'сому': 'KGS',
    # Казахский тенге
    'kzt': 'KZT', 'тенге': 'KZT', '₸': 'KZT',
    # Индийская рупия
    'inr': 'INR', 'рупия': 'INR', 'рупиях': 'INR', 'рупии': 'INR', 'рупий': 'INR', 'рупию': 'INR', '₹': 'INR',
    # Малайзийский ринггит
    'myr': 'MYR', 'ринггит': 'MYR', 'ринггитах': 'MYR', 'ринггиты': 'MYR', 'ринггитов': 'MYR', 'ринггита': 'MYR',
    # Узбекский сум
    'uzs': 'UZS', 'сум': 'UZS', 'сумах': 'UZS', 'сумов': 'UZS', 'сума': 'UZS',
    # Таджикский сомони
    'tjs': 'TJS', 'сомони': 'TJS',
    # Армянский драм
    'amd': 'AMD', 'драм': 'AMD', 'драмах': 'AMD', 'драмов': 'AMD',
    # Грузинский лари
    'gel': 'GEL', 'лари': 'GEL', '₾': 'GEL',
    # Украинская гривна
    'uah': 'UAH', 'гривна': 'UAH', 'гривнах': 'UAH', 'гривен': 'UAH', 'гривны': 'UAH', '₴': 'UAH',
    # Беларуский рубль
    'byn': 'BYN', 'белрубль': 'BYN',
    # Турецкая лира
    'try': 'TRY', 'лира': 'TRY', 'лирах': 'TRY', 'лиры': 'TRY', 'лир': 'TRY', 'лиру': 'TRY', '₺': 'TRY',
    # Дирхам ОАЭ
    'aed': 'AED', 'дирхам': 'AED', 'дирхамах': 'AED', 'дирхамы': 'AED', 'дирхама': 'AED',
    # Китайский юань
    'cny': 'CNY', 'юань': 'CNY', 'юанях': 'CNY', 'юаней': 'CNY', 'юаня': 'CNY', '¥': 'CNY',
    # Британский фунт
    'gbp': 'GBP', 'фунт': 'GBP', 'фунтах': 'GBP', 'фунтов': 'GBP', '£': 'GBP',
    # Швейцарский франк
    'chf': 'CHF', 'франк': 'CHF', 'франках': 'CHF', 'франков': 'CHF',
    # Тайский бат
    'thb': 'THB', 'бат': 'THB', 'батах': 'THB', 'баты': 'THB', 'батов': 'THB', '฿': 'THB',
}

# Функция нечеткого поиска валюты с распознаванием опечаток
def get_currency_code(word: str) -> str:
    word = word.lower().strip()
    
    # 1. Точное совпадение
    if word in CURRENCY_MAP:
        return CURRENCY_MAP[word]
    
    # 2. Поиск похожих слов (difflib)
    # cutoff=0.55 означает порог схожести не менее 55%
    matches = difflib.get_close_matches(word, CURRENCY_MAP.keys(), n=1, cutoff=0.55)
    if matches:
        best_match = matches[0]
        return CURRENCY_MAP[best_match]
    
    return None

async def fetch_rates():
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("rates", {})
                return None
    except Exception:
        return None

# ----------------------------------------------------
# Обработчики сообщений
# ----------------------------------------------------

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        await message.answer(
            "👑 **Привет, Владелец!**\n\n"
            "Тебе доступны панели управления доступом.\n"
            "Умный конвертер с распознаванием опечаток готов к работе!",
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )
        return

    if user_id in allowed_users:
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            "У тебя есть доступ к конвертеру валют! 🌍\n"
            "Пиши любые запросы (даже с опечатками!), например:\n"
            "• `984 соом в даларах`\n"
            "• `3924 рупии к ринит`",
            parse_mode="Markdown",
            reply_markup=user_keyboard
        )
    else:
        await message.answer(
            f"⛔ **Доступ ограничен.**\n\n"
            f"Ваш Telegram ID: `{user_id}`\n"
            f"Отправьте его администратору для доступа.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

# ----------------------------------------------------
# Инструкция (для всех, у кого есть доступ) и список пользователей (только админ)
# ----------------------------------------------------
INSTRUCTION_TEXT = """📖 ИНСТРУКЦИЯ ПО БОТУ

💱 Что это за бот?
Я конвертер валют. Пишешь сумму и две валюты, а я сразу показываю результат по актуальному курсу.

━━━━━━━━━━━━━━━
✍️ КАК ПИСАТЬ ЗАПРОС

Формат: сумма, валюта, которую переводим, слово «в» или «к», валюта, в которую переводим.

Примеры:
• 100 сом в долларах
• 5000 рублей к сому
• 250 евро в тенге
• 3924 рупии к ринггитам
• 50 usd to kgs

Слова между валютами можно писать любые из этих: в, к, на, to, in. Можно даже просто пробел.

━━━━━━━━━━━━━━━
🔢 ЕСЛИ НЕ УКАЗАТЬ СУММУ

Напиши только две валюты, и я переведу 1 единицу:
• рубль к сому
• доллар в евро

━━━━━━━━━━━━━━━
🔤 ОПЕЧАТКИ — НЕ ПРОБЛЕМА

Я понимаю слова даже с ошибками. Например, «984 соом в даларах» я пойму как «984 сом в долларах».

Если бот пишет, что не смог распознать валюту, попробуй написать слово точнее или используй код валюты (например, USD, KGS, RUB).

━━━━━━━━━━━━━━━
🌍 КАКИЕ ВАЛЮТЫ ЕСТЬ

• USD доллар США ($)
• EUR евро (€)
• RUB российский рубль (₽)
• KGS кыргызский сом
• KZT казахский тенге (₸)
• UZS узбекский сум
• TJS таджикский сомони
• AMD армянский драм
• GEL грузинский лари (₾)
• UAH украинская гривна (₴)
• BYN белорусский рубль
• TRY турецкая лира (₺)
• AED дирхам ОАЭ
• CNY китайский юань (¥)
• GBP британский фунт (£)
• CHF швейцарский франк
• INR индийская рупия (₹)
• MYR малайзийский ринггит
• THB тайский бат (฿)

Валюту пиши одним словом: «доллар», а не «доллар США».

━━━━━━━━━━━━━━━
💡 ВАЖНО ЗНАТЬ

• Дробные числа можно писать и через точку, и через запятую: 12,5 или 12.5
• Большие суммы можно писать с пробелами: 1 000 000
• Курсы международные и обновляются раз в сутки, поэтому в банке или обменнике курс может немного отличаться
• Если бот ответил, что сервер валют недоступен, просто повтори запрос через минуту

━━━━━━━━━━━━━━━
⌨️ КОМАНДЫ

/start  главное меню
/help  эта инструкция

Остались вопросы? Напиши администратору бота. 🙂"""

ADMIN_EXTRA_TEXT = """

━━━━━━━━━━━━━━━
👑 ТОЛЬКО ДЛЯ АДМИНИСТРАТОРА

Кнопки внизу экрана:
• 👥 Список пользователей показывает всех, у кого есть доступ к боту
• ➕ Добавить доступ: нажми и отправь Telegram ID человека цифрами
• ➖ Закрыть доступ: нажми и отправь Telegram ID человека, у которого нужно забрать доступ

Как узнать ID нового пользователя: пусть он напишет боту /start. Бот покажет ему его ID, и он отправит его тебе."""

@dp.message(lambda msg: msg.text == "📖 Инструкция")
@dp.message(Command("help"))
async def instruction_handler(message: types.Message):
    user_id = message.from_user.id

    if user_id != ADMIN_ID and user_id not in allowed_users:
        await message.answer(f"⛔ Доступ запрещен. Ваш ID: `{user_id}`", parse_mode="Markdown")
        return

    text = INSTRUCTION_TEXT
    if user_id == ADMIN_ID:
        text += ADMIN_EXTRA_TEXT
        await message.answer(text, reply_markup=admin_keyboard)
    else:
        await message.answer(text, reply_markup=user_keyboard)

@dp.message(lambda msg: msg.text == "👥 Список пользователей" and msg.from_user.id == ADMIN_ID)
async def show_users_list(message: types.Message):
    if not allowed_users:
        await message.answer(
            "👥 Список пользователей пуст.\n"
            "Дополнительных пользователей пока нет, доступ только у тебя.",
            reply_markup=admin_keyboard
        )
        return

    lines = [f"👥 Пользователи с доступом ({len(allowed_users)}):\n"]
    for i, uid in enumerate(sorted(allowed_users), start=1):
        name = ""
        try:
            # Пытаемся получить имя и ник (работает, если человек уже писал боту)
            chat = await bot.get_chat(uid)
            parts = [chat.first_name or "", chat.last_name or ""]
            name = " ".join(p for p in parts if p)
            if chat.username:
                name += f" (@{chat.username})"
            name = name.strip()
        except Exception:
            name = ""
        lines.append(f"{i}. {uid}" + (f" — {name}" if name else ""))

    await message.answer("\n".join(lines), reply_markup=admin_keyboard)

# Панель Админа: Нажатие "Добавить доступ"
@dp.message(lambda msg: msg.text == "➕ Добавить доступ" and msg.from_user.id == ADMIN_ID)
async def process_add_button(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_add_id)
    await message.answer("📥 Введи **Telegram ID** пользователя, которому нужно дать доступ:")

@dp.message(AdminStates.waiting_for_add_id)
async def process_add_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_id = int(message.text.strip())
        allowed_users.add(new_id)
        save_allowed_users(allowed_users)
        await message.answer(f"✅ Пользователь с ID `{new_id}` добавлен!", reply_markup=admin_keyboard)
    except ValueError:
        await message.answer("❌ Ошибка: ID должен состоять из цифр.")
    finally:
        await state.clear()

# Панель Админа: Нажатие "Закрыть доступ"
@dp.message(lambda msg: msg.text == "➖ Закрыть доступ" and msg.from_user.id == ADMIN_ID)
async def process_remove_button(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_remove_id)
    await message.answer("📤 Введи **Telegram ID** пользователя, у которого нужно забрать доступ:")

@dp.message(AdminStates.waiting_for_remove_id)
async def process_remove_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        remove_id = int(message.text.strip())
        if remove_id in allowed_users:
            allowed_users.remove(remove_id)
            save_allowed_users(allowed_users)
            await message.answer(f"🚫 Доступ для ID `{remove_id}` закрыт!", reply_markup=admin_keyboard)
        else:
            await message.answer("⚠️ Пользователя не было в списке.", reply_markup=admin_keyboard)
    except ValueError:
        await message.answer("❌ Ошибка: ID должен состоять из цифр.")
    finally:
        await state.clear()

# Главный конвертер с защитой и распознаванием опечаток
@dp.message()
async def convert_currency(message: types.Message):
    user_id = message.from_user.id

    if user_id != ADMIN_ID and user_id not in allowed_users:
        await message.answer(f"⛔ Доступ запрещен. Ваш ID: `{user_id}`", parse_mode="Markdown")
        return

    text = message.text.strip().lower()

    pattern = r"^(?:([\d\s\,\.]+)\s*)?([a-zA-Zа-яА-Я\$₽£€₴₸₺₾฿¥₩₫]+)\s*(?:в|к|на|to|in|\s)\s*([a-zA-Zа-яА-Я\$₽£€₴₸₺₾฿¥₩₫]+)$"
    match = re.match(pattern, text)

    if not match:
        await message.answer(
            "⚠️ Не удалось понять запрос.\n"
            "Попробуй написать в формате: **100 сом в долларах** или **рубль к сому**.",
            parse_mode="Markdown"
        )
        return

    amount_str, raw_from, raw_to = match.groups()

    amount = 1.0 if not amount_str else float(amount_str.replace(" ", "").replace(",", "."))

    # Распознаем валюты даже с ошибками в буквах
    code_from = get_currency_code(raw_from)
    code_to = get_currency_code(raw_to)

    if not code_from or not code_to:
        await message.answer(
            f"❌ Не удалось распознать валюту даже с умным поиском.\n"
            f"Проверь слова: `{raw_from}` или `{raw_to}`.",
            parse_mode="Markdown"
        )
        return

    rates = await fetch_rates()
    if not rates or code_from not in rates or code_to not in rates:
        await message.answer("❌ Сервер валют временно недоступен.")
        return

    amount_in_usd = amount / rates[code_from]
    result = amount_in_usd * rates[code_to]

    await message.answer(
        f"💱 **Результат конвертации:**\n\n"
        f"**{amount:,.2f} {code_from}** = **{result:,.2f} {code_to}**",
        parse_mode="Markdown"
    )

async def main():
    print("Бот с умным нечетким поиском валют запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())