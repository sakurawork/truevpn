import sqlite3
import time
import secrets
import uuid
import logging
import requests
from config import DB_PATH, BOT_TOKEN

def get_db(db_path=None):
    return sqlite3.connect(db_path or DB_PATH)

def init_db(db_path=None):
    conn = get_db(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            trial_used INTEGER DEFAULT 0,
            sub_expire_at INTEGER DEFAULT 0,
            token TEXT UNIQUE,
            source TEXT,
            is_blocked INTEGER DEFAULT 0,
            uuid TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            payment_id TEXT,
            status TEXT,
            gateway TEXT,
            created_at INTEGER,
            duration INTEGER DEFAULT 30
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS traffic_sources (
            source_id TEXT PRIMARY KEY,
            type TEXT,
            name TEXT,
            clicks INTEGER DEFAULT 0,
            created_at INTEGER,
            token TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            referrer_rewarded INTEGER DEFAULT 1,
            referred_rewarded INTEGER DEFAULT 1,
            created_at INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS referral_withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            created_at INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS used_promos (
            user_id INTEGER,
            promo_code TEXT,
            PRIMARY KEY (user_id, promo_code)
        )
    """)
    conn.commit()
    conn.close()

def reward_referrer(c, payer_id, amount, payer_username=None, bot_token=None):
    try:
        c.execute("SELECT source FROM users WHERE user_id = ?", (payer_id,))
        row = c.fetchone()
        if not row or not row[0]:
            return

        source = row[0]
        ref_id_str = None
        if source.startswith("ref_"):
            ref_id_str = source[4:]
        elif source.startswith("ref"):
            ref_id_str = source[3:]
        else:
            ref_id_str = source

        if ref_id_str and ref_id_str.isdigit():
            ref_id = int(ref_id_str)
            c.execute("SELECT username FROM users WHERE user_id = ?", (ref_id,))
            ref_row = c.fetchone()
            if ref_row:
                bonus = float(amount) * 0.20
                payer_disp = f"@{payer_username}" if payer_username else f"ID {payer_id}"
                token = bot_token or BOT_TOKEN
                if token:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    text = (
                        f"🎉 <b>Реферальное начисление!</b>\n\n"
                        f"Ваш реферал {payer_disp} оплатил подписку на сумму {amount} ₽.\n"
                        f"Вам начислено <b>{bonus:.2f} ₽</b> (20%) на реферальный баланс!"
                    )
                    payload = {"chat_id": ref_id, "text": text, "parse_mode": "HTML"}
                    try:
                        requests.post(url, json=payload, timeout=5)
                    except Exception as e:
                        logging.error(f"Failed to send reward message: {e}")
    except Exception as e:
        logging.error(f"Error rewarding referrer: {e}")

def get_or_create_user(user_id, username, source=None, first_name="", db_path=None):
    conn = get_db(db_path)
    c = conn.cursor()
    c.execute("SELECT trial_used, sub_expire_at, token, username, is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    if source:
        try:
            c.execute("INSERT INTO traffic_sources (source_id, type, name, clicks, created_at) VALUES (?, 'custom', ?, 1, ?) "
                      "ON CONFLICT(source_id) DO UPDATE SET clicks = clicks + 1",
                      (source, f"Источник: {source}", int(time.time())))
            conn.commit()
        except Exception as e:
            logging.error(f"Error updating traffic source {source}: {e}")

    if not row:
        token = secrets.token_hex(16)
        user_uuid = str(uuid.uuid4())
        c.execute("INSERT INTO users (user_id, username, trial_used, sub_expire_at, token, source, is_blocked, uuid) VALUES (?, ?, 0, 0, ?, ?, 0, ?)",
                  (user_id, username, token, source, user_uuid))
        conn.commit()
        trial_used = 0
        sub_expire_at = 0

        if source:
            ref_id_str = None
            if source.startswith("ref_"):
                ref_id_str = source[4:]
            elif source.startswith("ref"):
                ref_id_str = source[3:]
            if ref_id_str and ref_id_str.isdigit():
                ref_id = int(ref_id_str)
                if ref_id != user_id:
                    c.execute("SELECT user_id FROM users WHERE user_id = ?", (ref_id,))
                    if c.fetchone():
                        c.execute("SELECT referred_id FROM referrals WHERE referrer_id = ? AND referred_id = ?", (ref_id, user_id))
                        if not c.fetchone():
                            now = int(time.time())
                            c.execute("INSERT INTO referrals (referrer_id, referred_id, referrer_rewarded, referred_rewarded, created_at) VALUES (?, ?, 1, 1, ?)",
                                      (ref_id, user_id, now))
                            c.execute("SELECT sub_expire_at FROM users WHERE user_id = ?", (ref_id,))
                            ref_row = c.fetchone()
                            if ref_row:
                                ref_new = max(now, ref_row[0]) + 4 * 24 * 3600
                                c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (ref_new, ref_id))
                            new_expire = now + 4 * 24 * 3600
                            c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (new_expire, user_id))
                            sub_expire_at = new_expire
                            conn.commit()
                            display_name = first_name or (f"@{username}" if username else f"ID {user_id}")
                            if BOT_TOKEN:
                                try:
                                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                                    requests.post(url, json={
                                        "chat_id": ref_id,
                                        "text": f"👤 <b>Новый реферал!</b>\n\nПользователь <b>{display_name}</b> перешёл по вашей реферальной ссылке.\nВам начислено <b>4 дня</b> подписки.",
                                        "parse_mode": "HTML"
                                    }, timeout=5)
                                    requests.post(url, json={
                                        "chat_id": user_id,
                                        "text": "🎉 <b>Реферальная акция!</b>\n\nВы получаете <b>4 дня</b> подписки бесплатно по приглашению друга!",
                                        "parse_mode": "HTML"
                                    }, timeout=5)
                                except Exception as e:
                                    logging.error(f"Failed to send referral notifications: {e}")
    else:
        trial_used, sub_expire_at, token, _, is_blocked = row
        if is_blocked == 1:
            c.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
            conn.commit()

    conn.close()
    return trial_used, sub_expire_at, token
