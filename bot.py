import os
import sqlite3
import time
import secrets
import uuid
import logging
import asyncio
import requests
import json
import urllib.parse
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CRYPTOPAY_TOKEN,
    PLATEGA_KEY,
    PLATEGA_MERCHANT_ID,
    BASE_URL,
    MINI_APP_URL,
    BOT_USERNAME,
    DB_PATH,
    SUBSCRIPTION_CACHE_PATH,
    REQUIRED_CHANNEL,
    REQUIRED_CHANNEL_LINK,
)
from database import init_db, get_db, get_or_create_user, reward_referrer

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def is_subscribed(user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(chat_id="@" + REQUIRED_CHANNEL, user_id=user_id)
        status = getattr(member, "status", None)
        return status in ("creator", "administrator", "member")
    except Exception as e:
        logging.warning(f"[Subscription] user {user_id}: get_chat_member error: {e}")
        return True

def subscription_keyboard():
    kb = InlineKeyboardBuilder()
    if REQUIRED_CHANNEL_LINK:
        kb.button(text="📢 Подписаться", url=REQUIRED_CHANNEL_LINK)
    kb.button(text="✅ Проверить подписку", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

SUBSCRIPTION_TEXT = (
    "🔒 <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
    f"👉 Подпишитесь на <a href=\"{REQUIRED_CHANNEL_LINK}\">канал</a>, "
    "затем нажмите «Проверить подписку».\n\n"
    "Если вы отпишетесь — доступ к боту будет ограничен."
)

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not REQUIRED_CHANNEL:
            return await handler(event, data)
        user_id = None
        if isinstance(event, types.Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            if getattr(event, "data", None) == "check_sub":
                return await handler(event, data)
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        if not user_id:
            return await handler(event, data)

        if user_id in ADMIN_IDS:
            return await handler(event, data)

        subscribed = await is_subscribed(user_id)
        if subscribed:
            return await handler(event, data)

        if isinstance(event, types.Message):
            await event.answer(SUBSCRIPTION_TEXT, parse_mode="HTML", reply_markup=subscription_keyboard())
        elif isinstance(event, CallbackQuery):
            await event.answer("Сначала подпишитесь на канал!", show_alert=True)
            try:
                await event.message.edit_text(SUBSCRIPTION_TEXT, parse_mode="HTML", reply_markup=subscription_keyboard())
            except Exception:
                await event.message.answer(SUBSCRIPTION_TEXT, parse_mode="HTML", reply_markup=subscription_keyboard())
        return

dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())

class PromoState(StatesGroup):
    waiting_for_promo = State()

class ReferralState(StatesGroup):
    waiting_for_details = State()

class SupportState(StatesGroup):
    waiting_for_message = State()

def get_main_menu(user_id, username):
    trial_used, sub_expire_at, token = get_or_create_user(user_id, username)
    current_time = int(time.time())

    if sub_expire_at > current_time:
        expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(sub_expire_at))
        status_text = f"🟢 Активна (до {expire_str})"
    else:
        status_text = "🔴 Неактивна"

    welcome_text = (
        f"👋 <b>Добро пожаловать в сервис безопасного VPN!</b>\n\n"
        f"🛡 <b>Статус подписки:</b> {status_text}\n\n"
        f"⚡ Высокая скорость, обход любых блокировок и полная анонимность.\n"
        f"Выберите действие ниже:"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Mini App", web_app=WebAppInfo(url=MINI_APP_URL))
    kb.button(text="💳 Купить подписку", callback_data="buy_sub")
    kb.button(text="🔑 Моя подписка", callback_data="my_sub")

    if not trial_used:
        kb.button(text="🎁 Пробный период (3 дня)", callback_data="trial_sub")

    kb.button(text="🎟 Промокод", callback_data="promocode")
    kb.button(text="👥 Партнерская программа", callback_data="earn_referral")
    kb.button(text="📁 Получить ключи", callback_data="keys_page_0")
    kb.button(text="💬 Поддержка", callback_data="support")
    kb.button(text="📖 Инструкция", callback_data="help_instructions")
    kb.adjust(1, 2, 2, 2)
    return welcome_text, kb.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    parts = message.text.split()
    source = parts[1] if len(parts) > 1 else None
    get_or_create_user(user_id, username, source, message.from_user.first_name or "")
    text, reply_markup = get_main_menu(user_id, username)
    await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_subscribed(user_id):
        await callback.answer("✅ Подписка подтверждена!")
        text, reply_markup = get_main_menu(user_id, callback.from_user.username or "")
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)
        await callback.message.edit_text(SUBSCRIPTION_TEXT, parse_mode="HTML", reply_markup=subscription_keyboard())

@dp.callback_query(F.data == "my_sub")
async def cb_my_sub(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    trial_used, sub_expire_at, token = get_or_create_user(user_id, callback.from_user.username or "")
    current_time = int(time.time())
    if sub_expire_at > current_time:
        expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(sub_expire_at))
        status_text = f"🟢 <b>Активна</b> (до {expire_str})"
    else:
        status_text = "🔴 <b>Неактивна</b>"

    sub_url = f"{BASE_URL}/sub/{token}"
    text = (
        f"🔑 <b>Информация о подписке:</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📊 Статус: {status_text}\n"
        f"🎁 Тест период: {'Использован' if trial_used else 'Доступен'}\n\n"
        f"🔗 Ваша ссылка подписки (кликните, чтобы скопировать):\n"
        f"<code>{sub_url}</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "buy_sub")
async def cb_buy_sub(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="7 дней — 39 ₽", callback_data="buy_package_7")
    kb.button(text="14 дней — 69 ₽", callback_data="buy_package_14")
    kb.button(text="30 дней — 99 ₽", callback_data="buy_package_30")
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.edit_text(
        "💳 <b>Выберите срок действия подписки:</b>\n\n"
        "Мы предоставляем доступ к быстрым и стабильным туннелям без ограничений по скорости и трафику.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_package_"))
async def cb_buy_package(callback: CallbackQuery):
    duration = int(callback.data.split("_")[-1])
    price_map = {7: 39.0, 14: 69.0, 30: 99.0}
    price = price_map.get(duration, 99.0)
    text = (
        f"💳 <b>Оплата подписки на {duration} дней</b>\n"
        f"Стоимость: <b>{price:.0f} ₽</b>\n\n"
        "Выберите удобный способ оплаты:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Банковская карта (СБП)", callback_data=f"pay_method_platega_{duration}_{price}")
    kb.button(text="🪙 Криптовалюта", callback_data=f"pay_method_crypto_{duration}_{price}")
    kb.button(text="◀️ Назад", callback_data="buy_sub")
    kb.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_method_platega_"))
async def cb_pay_platega(callback: CallbackQuery):
    parts = callback.data.split("_")
    duration = int(parts[3])
    price = float(parts[4])
    user_id = callback.from_user.id
    headers = {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_KEY,
        "Content-Type": "application/json"
    }
    order_id = f"vpn_{user_id}_{duration}_{int(time.time())}"
    payload = {
        "paymentMethod": 2,
        "id": order_id,
        "paymentDetails": {
            "amount": price,
            "currency": "RUB"
        },
        "description": f"Подписка VPN на {duration} дней",
        "callbackUrl": f"{BASE_URL}/webhook/platega",
        "successUrl": f"https://t.me/{BOT_USERNAME}",
        "failUrl": f"https://t.me/{BOT_USERNAME}"
    }
    try:
        res = requests.post("https://app.platega.io/v2/transaction/process", json=payload, headers=headers, timeout=10)
        if res.status_code in [200, 201]:
            data = res.json()
            pay_url = data.get("url")
            payment_id = data.get("transactionId")
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO payments (user_id, amount, payment_id, status, gateway, created_at, duration) VALUES (?, ?, ?, 'pending', 'platega', ?, ?)",
                      (user_id, price, payment_id, int(time.time()), duration))
            conn.commit()
            conn.close()
            kb = InlineKeyboardBuilder()
            kb.button(text="🔗 Перейти к оплате", url=pay_url)
            await callback.message.answer("Ссылка на оплату СБП создана! Нажмите кнопку ниже:", reply_markup=kb.as_markup())
        else:
            await callback.message.answer(f"❌ Ошибка платежной системы (код {res.status_code}). Пожалуйста, попробуйте позже.")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка соединения с платежным шлюзом: {e}")
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_method_crypto_"))
async def cb_pay_cryptobot(callback: CallbackQuery):
    parts = callback.data.split("_")
    duration = int(parts[3])
    price = float(parts[4])
    user_id = callback.from_user.id
    crypto_amount_map = {7: "0.4", 14: "0.7", 30: "1.1"}
    crypto_amount = crypto_amount_map.get(duration, "1.1")
    headers = {"Crypto-Pay-API-Token": CRYPTOPAY_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": crypto_amount,
        "description": f"Подписка VPN на {duration} дней",
        "payload": str(user_id),
        "allow_anonymous": False
    }
    try:
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            invoice = data.get("result", {})
            pay_url = invoice.get("pay_url")
            invoice_id = str(invoice.get("invoice_id"))
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO payments (user_id, amount, payment_id, status, gateway, created_at, duration) VALUES (?, ?, ?, 'pending', 'cryptobot', ?, ?)",
                      (user_id, price, invoice_id, int(time.time()), duration))
            conn.commit()
            conn.close()
            kb = InlineKeyboardBuilder()
            kb.button(text="🔗 Оплатить CryptoBot", url=pay_url)
            await callback.message.answer("Счет на оплату через CryptoBot создан! Нажмите кнопку ниже:", reply_markup=kb.as_markup())
        else:
            await callback.message.answer("❌ Ошибка платежной системы. Пожалуйста, попробуйте позже.")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка соединения с CryptoBot: {e}")
    await callback.answer()

@dp.callback_query(F.data == "trial_sub")
async def cb_trial_sub(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT trial_used, sub_expire_at, token FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row[0] == 1:
        await callback.message.answer("❌ Вы уже использовали пробный период.")
        await callback.answer()
        conn.close()
        return

    current_time = int(time.time())
    new_expire_at = current_time + (3 * 24 * 3600)
    c.execute("UPDATE users SET trial_used = 1, sub_expire_at = ? WHERE user_id = ?", (new_expire_at, user_id))
    conn.commit()
    conn.close()

    expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(new_expire_at))
    await callback.message.answer(f"🎉 <b>Пробный период активирован!</b>\n\nВаша подписка действует до <b>{expire_str}</b>.\nНажмите «Моя подписка», чтобы получить ссылку для подключения.", parse_mode="HTML")
    text, reply_markup = get_main_menu(user_id, callback.from_user.username or "")
    await callback.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    await callback.answer()

@dp.callback_query(F.data == "help_instructions")
async def cb_instructions(callback: CallbackQuery):
    text = (
        "📖 <b>Инструкция по подключению VPN:</b>\n\n"
        "1. Скачайте приложение <b>v2rayNG</b> (Android), <b>V2Box / Streisand / Happ</b> (iOS) или <b>Hiddify / Nekoray</b> (Windows/macOS).\n"
        "2. Перейдите в раздел <b>«🔑 Моя подписка»</b> и скопируйте вашу персональную ссылку подписки.\n"
        "3. Откройте приложение, нажмите <b>«+»</b> или «Импорт» и выберите <b>«Добавить подписку из буфера обмена»</b>.\n"
        "4. Обновите подписку и подключитесь к любой локации!"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text, reply_markup = get_main_menu(user_id, username)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("keys_page_"))
async def cb_keys_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    locations = []
    if os.path.exists(SUBSCRIPTION_CACHE_PATH):
        try:
            with open(SUBSCRIPTION_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                locations = data.get("locations", [])
        except Exception as e:
            logging.error(f"Error loading cache: {e}")

    if not locations:
        await callback.message.edit_text("❌ Список серверов временно недоступен.")
        await callback.answer()
        return

    items_per_page = 5
    total_items = len(locations)
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_locations = locations[start_idx:end_idx]

    kb = InlineKeyboardBuilder()
    for idx, loc in enumerate(page_locations):
        global_idx = start_idx + idx
        kb.button(text=loc["name"], callback_data=f"key_show_{global_idx}_{page}")
    kb.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="◀️ Назад", callback_data=f"keys_page_{page-1}"))
    else:
        nav_buttons.append(types.InlineKeyboardButton(text="⏹", callback_data="noop"))

    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{(total_items + items_per_page - 1)//items_per_page}", callback_data="noop"))

    if end_idx < total_items:
        nav_buttons.append(types.InlineKeyboardButton(text="Вперед ▶️", callback_data=f"keys_page_{page+1}"))
    else:
        nav_buttons.append(types.InlineKeyboardButton(text="⏹", callback_data="noop"))

    kb.row(*nav_buttons)
    kb.row(types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    text = "📁 <b>Выберите локацию для получения ключа:</b>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("key_show_"))
async def cb_key_show(callback: CallbackQuery):
    parts = callback.data.split("_")
    global_idx = int(parts[2])
    page = int(parts[3])
    if not os.path.exists(SUBSCRIPTION_CACHE_PATH):
        await callback.message.edit_text("❌ Ошибка: файл подписки не найден.")
        await callback.answer()
        return
    try:
        with open(SUBSCRIPTION_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            locations = data.get("locations", [])
            loc = locations[global_idx]
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка получения ключа: {e}")
        await callback.answer()
        return

    text = (
        f"📍 <b>{loc['name']}</b>\n\n"
        f"Скопируйте ключ ниже (нажмите на текст, чтобы скопировать):\n\n"
        f"<code>{loc['key']}</code>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад к списку", callback_data=f"keys_page_{page}")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "promocode")
async def cb_promocode(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎟 <b>Активация промокода</b>\n\nВведите ваш промокод:")
    await state.set_state(PromoState.waiting_for_promo)
    await callback.answer()

@dp.message(PromoState.waiting_for_promo)
async def process_promo(message: types.Message, state: FSMContext):
    promo = (message.text or "").strip().lower()
    user_id = message.from_user.id
    valid_promos = {"true3d": 3, "true_3d": 3, "welcome": 3}

    if promo in valid_promos:
        days = valid_promos[promo]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM used_promos WHERE user_id = ? AND promo_code = ?", (user_id, promo))
        if c.fetchone():
            await message.answer("❌ Вы уже активировали этот промокод.")
        else:
            c.execute("SELECT sub_expire_at FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            current_time = int(time.time())
            old_expire = row[0] if row else 0
            new_expire = max(current_time, old_expire) + (days * 24 * 3600)
            c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (new_expire, user_id))
            c.execute("INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)", (user_id, promo))
            conn.commit()
            await message.answer(
                f"🎉 <b>Промокод успешно активирован!</b>\n\n"
                f"Подписка продлена на {days} дня (до {time.strftime('%d.%m.%Y %H:%M', time.localtime(new_expire))})."
            )
        conn.close()
    else:
        await message.answer("❌ Промокод не найден.")
    await state.clear()

@dp.callback_query(F.data == "earn_referral")
async def cb_earn(callback: CallbackQuery):
    user_id = callback.from_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE source = ? OR source = ?", (str(user_id), f"ref{user_id}"))
    ref_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    promo_count = c.fetchone()[0]
    c.execute("""
        SELECT SUM(payments.amount) * 0.20
        FROM payments
        JOIN users ON payments.user_id = users.user_id
        WHERE (users.source = ? OR users.source = ?)
          AND payments.status IN ('success', 'completed', 'paid')
    """, (str(user_id), f"ref{user_id}"))
    total_earned = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM referral_withdrawals WHERE user_id = ?", (user_id,))
    total_withdrawn = c.fetchone()[0] or 0.0
    net_balance = max(0.0, total_earned - total_withdrawn)
    conn.close()

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
    text = (
        f"🎁 <b>Приведи друга — получи 4 дня VPN!</b>\n\n"
        f"Отправь другому человеку свою ссылку.\n"
        f"Когда он напишет /start по ней — оба получите <b>+4 дня</b> подписки бесплатно.\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>Твоя статистика:</b>\n"
        f"👤 Приглашено: <code>{ref_count}</code> чел.\n"
        f"🎁 Начислено за акцию: <code>{promo_count * 4}</code> дней\n"
        f"💰 Реферальный баланс: <code>{net_balance:.2f} ₽</code>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Вывести баланс", callback_data="ref_withdraw")
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "ref_withdraw")
async def cb_ref_withdraw(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT SUM(payments.amount) * 0.20
        FROM payments
        JOIN users ON payments.user_id = users.user_id
        WHERE (users.source = ? OR users.source = ?)
          AND payments.status IN ('success', 'completed', 'paid')
    """, (str(user_id), f"ref{user_id}"))
    total_earned = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM referral_withdrawals WHERE user_id = ?", (user_id,))
    total_withdrawn = c.fetchone()[0] or 0.0
    net_balance = max(0.0, total_earned - total_withdrawn)
    conn.close()

    if net_balance < 100.0:
        await callback.message.answer(
            f"❌ <b>Недостаточно средств.</b>\n\n"
            f"Минимальная сумма для вывода составляет 100 ₽. Ваш баланс: {net_balance:.2f} ₽.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"💳 <b>Вывод реферального баланса</b>\n\n"
        f"Доступно к выводу: <b>{net_balance:.2f} ₽</b>\n\n"
        f"Пожалуйста, введите реквизиты для вывода (номер карты СБП, банк и имя получателя, либо адрес USDT):",
        parse_mode="HTML"
    )
    await state.set_state(ReferralState.waiting_for_details)
    await callback.answer()

@dp.message(ReferralState.waiting_for_details)
async def process_ref_withdraw_details(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    details = message.text
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT SUM(payments.amount) * 0.20
        FROM payments
        JOIN users ON payments.user_id = users.user_id
        WHERE (users.source = ? OR users.source = ?)
          AND payments.status IN ('success', 'completed', 'paid')
    """, (str(user_id), f"ref{user_id}"))
    total_earned = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM referral_withdrawals WHERE user_id = ?", (user_id,))
    total_withdrawn = c.fetchone()[0] or 0.0
    net_balance = max(0.0, total_earned - total_withdrawn)

    if net_balance < 100.0:
        await message.answer("❌ Ошибка: баланс меньше 100 ₽.")
        await state.clear()
        conn.close()
        return

    c.execute("INSERT INTO referral_withdrawals (user_id, amount, created_at) VALUES (?, ?, ?)",
              (user_id, net_balance, int(time.time())))
    conn.commit()
    conn.close()

    admin_text = (
        f"🚨 <b>Заявка на вывод средств!</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: <code>{user_id}</code>)\n"
        f"💰 Сумма: <b>{net_balance:.2f} ₽</b>\n"
        f"📋 Реквизиты:\n<code>{details}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Failed to send withdraw request to admin {admin_id}: {e}")

    await message.answer(
        f"✅ <b>Заявка на вывод {net_balance:.2f} ₽ успешно создана!</b>\n\n"
        f"Администратор обработает перевод в ближайшее время.",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(Command("admin"))
@dp.message(Command("stats"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    now = int(time.time())
    today_start = now - (now % 86400)
    month_start = now - (30 * 86400)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE trial_used = 1")
    trial_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE sub_expire_at > ?", (now,))
    active_subs = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM payments WHERE status IN ('success','completed','paid') AND created_at >= ?", (today_start,))
    income_today = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM payments WHERE status IN ('success','completed','paid') AND created_at >= ?", (month_start,))
    income_month = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM payments WHERE status IN ('success','completed','paid')")
    income_all = c.fetchone()[0] or 0.0
    conn.close()

    text = (
        "📊 <b>Статистика сервиса:</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"🎁 Использовали пробный: <code>{trial_users}</code>\n"
        f"🟢 Активных подписок: <code>{active_subs}</code>\n\n"
        f"💰 Доход за сегодня: <code>{income_today:.0f} ₽</code>\n"
        f"💰 Доход за 30 дней: <code>{income_month:.0f} ₽</code>\n"
        f"💰 Доход за все время: <code>{income_all:.0f} ₽</code>\n\n"
        "<b>Команды администратора:</b>\n"
        "• <code>/approve &lt;user_id&gt; &lt;days&gt;</code> — выдать подписку\n"
        "• <code>/broadcast &lt;filter&gt; &lt;text&gt;</code> — рассылка (paid/trial/all)"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("approve"))
async def cmd_approve(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Формат: <code>/approve &lt;user_id&gt; &lt;days&gt;</code>", parse_mode="HTML")
        return
    try:
        target_uid = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("❌ user_id и days должны быть числами.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT sub_expire_at, token FROM users WHERE user_id = ?", (target_uid,))
    row = c.fetchone()
    current_time = int(time.time())
    old_expire = row[0] if row else 0
    new_expire = max(current_time, old_expire) + (days * 24 * 3600)

    if row:
        c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (new_expire, target_uid))
    else:
        tok = secrets.token_hex(16)
        u_uuid = str(uuid.uuid4())
        c.execute("INSERT INTO users (user_id, username, trial_used, sub_expire_at, token, source, is_blocked, uuid) VALUES (?, '', 0, ?, ?, NULL, 0, ?)",
                  (target_uid, new_expire, tok, u_uuid))
    conn.commit()
    conn.close()

    expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(new_expire))
    await message.answer(f"✅ Подписка для <code>{target_uid}</code> продлена на <b>{days}</b> дн. (до {expire_str}).", parse_mode="HTML")
    try:
        await bot.send_message(
            target_uid,
            f"🎉 <b>Вам начислена подписка!</b>\n\nСрок действия: <b>{days} дней</b> (до {expire_str}).",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"⚠️ Пользователь не получил уведомление: {e}")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "⚠️ Формат: <code>/broadcast &lt;filter&gt; &lt;text&gt;</code>\n\n"
            "<b>Фильтры:</b>\n"
            "• <code>paid</code> — купившие подписку\n"
            "• <code>trial</code> — пробный период\n"
            "• <code>all</code> — все пользователи",
            parse_mode="HTML"
        )
        return
    filter_key = parts[1].lower()
    text = parts[2]
    now = int(time.time())
    conn = get_db()
    c = conn.cursor()
    if filter_key == "paid":
        c.execute("SELECT DISTINCT u.user_id FROM users u JOIN payments p ON p.user_id = u.user_id WHERE p.status IN ('success','completed','paid') AND u.sub_expire_at > ?", (now,))
    elif filter_key == "trial":
        c.execute("SELECT user_id FROM users WHERE trial_used = 1 AND sub_expire_at > ? AND user_id NOT IN (SELECT DISTINCT user_id FROM payments WHERE status IN ('success','completed','paid'))", (now,))
    else:
        c.execute("SELECT user_id FROM users WHERE sub_expire_at > ?", (now,))
    user_ids = [row[0] for row in c.fetchall()]
    conn.close()

    sent_ok = 0
    blocked = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent_ok += 1
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                blocked += 1
            else:
                failed += 1
        await asyncio.sleep(0.05)

    await message.answer(
        f"📢 <b>Рассылка завершена</b> (фильтр: <code>{filter_key}</code>)\n\n"
        f"✅ Отправлено: <code>{sent_ok}</code>\n"
        f"🚫 Заблокировали: <code>{blocked}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await cmd_start(message)

@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "💬 <b>Связь с поддержкой</b>\n\n"
        "Напишите ваше сообщение или вопрос ниже. Администратор ответит вам прямо в этом чате!\n\n"
        "<i>Для отмены нажмите кнопку ниже:</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Выйти из чата", callback_data="exit_support").as_markup()
    )
    await state.set_state(SupportState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "exit_support")
async def cb_exit_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text, reply_markup = get_main_menu(user_id, username)
    await callback.message.answer("Вы вышли из чата с поддержкой.", reply_markup=reply_markup)
    await callback.answer()

@dp.message(SupportState.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS and message.reply_to_message:
        await handle_admin_reply(message)
        return
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    text = message.text or "[Медиа/Файл]"

    admin_text = (
        f"💬 <b>Новое сообщение в поддержку!</b>\n\n"
        f"👤 Отправитель: @{username} (ID: <code>{user_id}</code>)\n\n"
        f"📝 Текст:\n{text}\n\n"
        f"<i>Ответьте на это сообщение (Reply), чтобы написать ответ пользователю.</i>"
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.text:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            else:
                sent_msg = await message.forward(admin_id)
                await bot.send_message(
                    admin_id,
                    f"👤 Выше переслано медиа от @{username} (ID: <code>{user_id}</code>)\n"
                    f"<i>Ответьте на ЭТО сообщение, чтобы написать ответ.</i>",
                    parse_mode="HTML",
                    reply_to_message_id=sent_msg.message_id
                )
        except Exception as e:
            logging.error(f"Failed to send support message to admin {admin_id}: {e}")

    await message.answer(
        "✅ <b>Сообщение отправлено поддержке!</b>\n\n"
        "Мы ответим вам в ближайшее время. Вы можете продолжать писать сообщения здесь.",
        parse_mode="HTML"
    )

@dp.message(F.reply_to_message)
async def handle_admin_reply(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return

    reply = message.reply_to_message
    target_user_id = None
    import re
    if reply.text:
        match = re.search(r'ID:\s*<code>(\d+)</code>', reply.text)
        if not match:
            match = re.search(r'ID:\s*(\d+)', reply.text)
        if match:
            target_user_id = int(match.group(1))

    if not target_user_id and reply.forward_from:
        target_user_id = reply.forward_from.id

    if not target_user_id:
        text_to_search = reply.text or reply.caption or ""
        match = re.search(r'ID:\s*<code>(\d+)</code>', text_to_search)
        if match:
            target_user_id = int(match.group(1))

    if not target_user_id:
        return

    try:
        await bot.send_message(
            target_user_id,
            f"💬 <b>Ответ от техподдержки:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ успешно отправлен пользователю (ID: {target_user_id}).")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки ответа пользователю: {e}")

async def main():
    init_db()
    try:
        from aiogram.types import MenuButtonWebApp
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
        )
    except Exception as e:
        logging.error(f"Error setting Menu button: {e}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
