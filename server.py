import os
import base64
import json
import sqlite3
import time
import secrets
import uuid
import hashlib
import hmac
import urllib.parse
import requests
import asyncio
from fastapi import FastAPI, Request, HTTPException, Query, Header, WebSocket
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    BOT_TOKEN,
    CRYPTOPAY_TOKEN,
    PLATEGA_KEY,
    PLATEGA_MERCHANT_ID,
    BASE_URL,
    BOT_USERNAME,
    DB_PATH,
    TUNNELS_METADATA,
    SUBSCRIPTION_CACHE_PATH,
    SERVER_HOST,
    REALITY_PUBLIC_KEY,
    REALITY_SHORT_IDS,
    API_PORT,
    API_HOST,
)
from database import init_db, get_db, reward_referrer

def generate_user_country_uuid(user_uuid, country_name):
    try:
        ns = uuid.UUID(user_uuid)
        return str(uuid.uuid5(ns, country_name))
    except Exception:
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, f"{user_uuid}-{country_name}"))

app = FastAPI(title="TrueVPN Backend & Subscription API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/tunnel-{index}-ws")
async def websocket_tunnel(websocket: WebSocket, index: int):
    await websocket.accept()
    local_port = 10001 + index
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", local_port)
        
        async def ws_to_xray():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    writer.write(data)
                    await writer.drain()
            except Exception:
                pass
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
                
        async def xray_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except Exception:
                pass
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass
                
        await asyncio.gather(ws_to_xray(), xray_to_ws())
    except Exception as e:
        print(f"[-] WebSocket proxy error: {e}")

def send_telegram_msg(chat_id, text, token=None):
    tk = token or BOT_TOKEN
    if not tk:
        return
    url = f"https://api.telegram.org/bot{tk}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[-] Failed to send Telegram message: {e}")

def verify_init_data(init_data: str) -> dict:
    if not init_data or not BOT_TOKEN:
        return {}
    try:
        parsed = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        data_dict = dict(parsed)
        
        hash_val = data_dict.pop("hash", None)
        if not hash_val:
            return {}
            
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_val:
            return {}
            
        user_raw = data_dict.get("user")
        if user_raw:
            user_info = json.loads(user_raw)
            if "start_param" in data_dict:
                user_info["_start_param"] = data_dict["start_param"]
            return user_info
        return {}
    except Exception as e:
        print(f"[-] InitData verification failed: {e}")
        return {}

@app.get("/sub/{token}")
async def get_subscription(token: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, trial_used, sub_expire_at, uuid, is_blocked FROM users WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    user_id, trial_used, sub_expire_at, user_uuid, is_blocked = row
    current_time = int(time.time())

    if is_blocked or sub_expire_at <= current_time:
        info_link = f"vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?security=none#{urllib.parse.quote('❌ Подписка истекла / Не активна')}"
        base64_sub = base64.b64encode(info_link.encode("utf-8")).decode("utf-8")
        headers = {
            "Content-Disposition": "attachment; filename=\"TrueVPN\"; filename*=UTF-8''TrueVPN",
            "Subscription-Userinfo": "upload=0; download=0; total=1099511627776; expire=0",
            "profile-update-interval": "1",
            "profile-title": "TrueVPN (Expired)"
        }
        return PlainTextResponse(content=base64_sub, headers=headers)

    if not user_uuid:
        user_uuid = str(uuid.uuid4())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET uuid = ? WHERE user_id = ?", (user_uuid, user_id))
        conn.commit()
        conn.close()

    links = []
    
    pbk = REALITY_PUBLIC_KEY
    sids = REALITY_SHORT_IDS or ["e39882243b75ee58"]
    
    if pbk:
        for idx, sid in enumerate(sids):
            name = f"TrueVPN Reality #{idx+1}"
            link = (
                f"vless://{user_uuid}@{SERVER_HOST}:8443"
                f"?encryption=none&type=tcp&security=reality"
                f"&flow=xtls-rprx-vision&pbk={pbk}"
                f"&fp=chrome&sni=gateway.icloud.com&sid={sid}&spx=%2F"
                f"#{urllib.parse.quote(name)}"
            )
            links.append(link)

    if os.path.exists(TUNNELS_METADATA):
        try:
            with open(TUNNELS_METADATA, "r", encoding="utf-8") as f:
                tunnels = json.load(f)
                for idx, t in enumerate(tunnels):
                    port = t.get("port", 10001 + idx)
                    ws_path = t.get("path", f"/tunnel-{idx}-ws")
                    encoded_name = urllib.parse.quote(t.get("name", f"Server #{idx+1}"))
                    link = (
                        f"vless://{user_uuid}@{SERVER_HOST}:{port}"
                        f"?encryption=none&type=ws"
                        f"&path={urllib.parse.quote(ws_path)}&security=none"
                        f"#{encoded_name}"
                    )
                    links.append(link)
        except Exception as e:
            print(f"[-] Error loading tunnels metadata: {e}")

    if not links:
        links = [
            f"vless://{user_uuid}@{SERVER_HOST}:10001?encryption=none&type=ws&path=%2Ftunnel-0-ws&security=none#TrueVPN%20Main"
        ]

    sub_content = "\n".join(links)
    base64_sub = base64.b64encode(sub_content.encode("utf-8")).decode("utf-8")

    profile_name = "TrueVPN"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{profile_name}\"; filename*=UTF-8''{profile_name}",
        "Subscription-Userinfo": f"upload=0; download=0; total=1099511627776; expire={sub_expire_at}",
        "profile-update-interval": "12",
        "profile-title": profile_name
    }
    return PlainTextResponse(content=base64_sub, headers=headers)

@app.get("/api/status")
async def get_user_status(initData: str = Query(None)):
    user_info = verify_init_data(initData)
    if not user_info:
        raise HTTPException(status_code=403, detail="Invalid Telegram InitData")
        
    user_id = user_info.get("id")
    username = user_info.get("username", "")
    first_name = user_info.get("first_name", "")

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT trial_used, sub_expire_at, token, is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if not row:
        token = secrets.token_hex(16)
        user_uuid = str(uuid.uuid4())
        source = user_info.get("_start_param", "") or None
        c.execute("INSERT INTO users (user_id, username, trial_used, sub_expire_at, token, is_blocked, uuid, source) VALUES (?, ?, 0, 0, ?, 0, ?, ?)",
                  (user_id, username, token, user_uuid, source))
        conn.commit()
        trial_used = 0
        sub_expire_at = 0
    else:
        trial_used, sub_expire_at, token, is_blocked = row

    conn.close()

    return {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "trial_used": trial_used,
        "sub_expire_at": sub_expire_at,
        "token": token
    }

@app.get("/api/locations")
async def get_locations(initData: str = Query(...)):
    user_info = verify_init_data(initData)
    if not user_info:
        raise HTTPException(status_code=403, detail="Invalid InitData")
        
    locations = []
    if os.path.exists(SUBSCRIPTION_CACHE_PATH):
        try:
            with open(SUBSCRIPTION_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                locations = data.get("locations", [])
        except Exception:
            pass
            
    return {"ok": True, "locations": locations}

@app.get("/import/hiddify")
async def import_hiddify(url: str):
    hiddify_url = f"hiddify://import/{url}"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Opening Hiddify...</title>
    <meta http-equiv="refresh" content="0; url={hiddify_url}">
    <script>
        window.location.href = "{hiddify_url}";
    </script>
</head>
<body>
    <p>Opening Hiddify... If nothing happens, <a href="{hiddify_url}">click here</a>.</p>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/import/happ")
async def import_happ(url: str):
    happ_url = f"happ://add/{url}"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Opening Happ...</title>
    <meta http-equiv="refresh" content="0; url={happ_url}">
    <script>
        window.location.href = "{happ_url}";
    </script>
</head>
<body>
    <p>Opening Happ... If nothing happens, <a href="{happ_url}">click here</a>.</p>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.post("/api/trial")
async def activate_trial(initData: str = Query(...)):
    user_info = verify_init_data(initData)
    if not user_info:
        raise HTTPException(status_code=403, detail="Invalid InitData")
        
    user_id = user_info.get("id")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT trial_used, sub_expire_at FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    trial_used, sub_expire_at = row
    if trial_used == 1:
        conn.close()
        return {"ok": False, "error": "Trial already used"}
        
    current_time = int(time.time())
    new_expire_at = current_time + (3 * 24 * 3600)
    c.execute("UPDATE users SET trial_used = 1, sub_expire_at = ? WHERE user_id = ?", (new_expire_at, user_id))
    conn.commit()
    conn.close()
    
    return {"ok": True, "sub_expire_at": new_expire_at}

class CreatePaymentRequest(BaseModel):
    initData: str
    duration: int
    method: str

@app.post("/api/pay/create")
async def create_payment(req_data: CreatePaymentRequest):
    user_info = verify_init_data(req_data.initData)
    if not user_info:
        raise HTTPException(status_code=403, detail="Invalid InitData")
        
    user_id = user_info.get("id")
    duration = req_data.duration
    method = req_data.method

    price_map = {7: 39.0, 14: 69.0, 30: 99.0}
    price = price_map.get(duration, 99.0)

    if method == "platega":
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

                return {"ok": True, "pay_url": pay_url}
            else:
                return {"ok": False, "error": f"Payment gateway error ({res.status_code})"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif method == "cryptobot":
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

                return {"ok": True, "pay_url": pay_url}
            else:
                return {"ok": False, "error": "CryptoBot error"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "Unknown payment method"}

@app.post("/webhook/platega")
async def webhook_platega(req: Request):
    try:
        data = await req.json()
        payment_id = data.get("transactionId") or data.get("id")
        status = data.get("status")

        if status in ["CONFIRMED", "SUCCESS", "PAID", "completed"]:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT user_id, amount, duration, status FROM payments WHERE payment_id = ? OR payment_id = ?", (str(payment_id), str(data.get("transactionId"))))
            row = c.fetchone()
            
            if row and row[3] != "success":
                user_id, amount, duration, _ = row
                duration_days = duration if duration else 30
                
                c.execute("UPDATE payments SET status = 'success' WHERE payment_id = ?", (str(payment_id),))
                c.execute("SELECT sub_expire_at, username FROM users WHERE user_id = ?", (user_id,))
                user_row = c.fetchone()
                
                if user_row:
                    current_time = int(time.time())
                    old_expire = user_row[0]
                    payer_username = user_row[1]
                    
                    new_expire = max(current_time, old_expire) + (duration_days * 24 * 3600)
                    c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (new_expire, user_id))
                    conn.commit()
                    
                    reward_referrer(c, user_id, amount, payer_username)
                    conn.commit()

                    expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(new_expire))
                    msg = "🎉 <b>Оплата успешно получена!</b>\n\nПодписка продлена на <b>" + str(duration_days) + " дней</b> (до " + str(expire_str) + ").\nПриятного пользования!"
                    send_telegram_msg(user_id, msg)
    except Exception as e:
        print(f"[-] Platega webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/webhook/cryptobot")
async def webhook_cryptobot(req: Request, crypto_pay_signature: str = Header(None, alias="crypto-pay-api-signature")):
    try:
        body = await req.body()
        if crypto_pay_signature and CRYPTOPAY_TOKEN:
            secret = hashlib.sha256(CRYPTOPAY_TOKEN.encode()).digest()
            hmac_check = hmac.new(secret, body, hashlib.sha256).hexdigest()
            if hmac_check != crypto_pay_signature:
                raise HTTPException(status_code=400, detail="Invalid signature")

        data = json.loads(body.decode("utf-8"))
        if data.get("update_type") == "invoice_paid":
            payload_data = data.get("payload", {})
            invoice_id = str(payload_data.get("invoice_id"))
            
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT user_id, amount, duration, status FROM payments WHERE payment_id = ?", (invoice_id,))
            row = c.fetchone()
            
            if row and row[3] != "success":
                user_id, amount, duration, _ = row
                duration_days = duration if duration else 30
                
                c.execute("UPDATE payments SET status = 'success' WHERE payment_id = ?", (invoice_id,))
                c.execute("SELECT sub_expire_at, username FROM users WHERE user_id = ?", (user_id,))
                user_row = c.fetchone()
                
                if user_row:
                    current_time = int(time.time())
                    old_expire = user_row[0]
                    payer_username = user_row[1]
                    
                    new_expire = max(current_time, old_expire) + (duration_days * 24 * 3600)
                    c.execute("UPDATE users SET sub_expire_at = ? WHERE user_id = ?", (new_expire, user_id))
                    conn.commit()
                    
                    reward_referrer(c, user_id, amount, payer_username)
                    conn.commit()

                    expire_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(new_expire))
                    msg = "🎉 <b>Оплата через CryptoBot получена!</b>\n\nПодписка продлена на <b>" + str(duration_days) + " дней</b> (до " + str(expire_str) + ")."
                    send_telegram_msg(user_id, msg)
            conn.close()
        return {"ok": True}
    except Exception as e:
        print(f"[-] CryptoBot webhook error: {e}")
        return {"ok": False, "error": str(e)}
@app.get("/app", response_class=HTMLResponse)
async def get_app():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return HTMLResponse("<h2>TrueVPN Mini App Portal</h2>")

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("server:app", host=API_HOST, port=API_PORT, reload=False)
