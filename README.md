# TrueVPN

[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.4+-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://aiogram.dev)
[![Xray Core](https://img.shields.io/badge/Xray_Core-1.8+-0052CC?style=flat)](https://xtls.github.io)

TrueVPN is a high-performance, automated Telegram bot and subscription sales management platform powered by Xray Core. It provides end-to-end automation for VPN services: client onboarding, automated payments, dynamic VLESS and Reality configuration generation, real-time node synchronization, Telegram Mini App client portal, and multi-tier referral revenue sharing.

---

## Key Features

* **Automated Provisioning & Cryptographic Access**:
  * Dynamic generation of deterministic VLESS user UUIDs and XTLS-Vision flow credentials upon payment or trial activation.
  * Real-time subscription status validation and automatic revocation for expired profiles.
* **Dynamic Multi-Node Synchronization**:
  * Real-time sync engine pulling upstream server pools and compiling local inbounds, outbounds, and routing rules for Xray Core.
  * Native support for VLESS + Reality (TCP) and VLESS + WebSocket fallback tunnels.
* **Telegram Mini App Web Portal**:
  * Built-in mobile-responsive Web App for viewing subscription validity, copying keys, and one-tap import into client applications.
* **Multi-Gateway Billing**:
  * CryptoBot integration supporting USDT, TON, BTC, and altcoins with HMAC-verified webhook confirmations.
  * Platega integration supporting SBP (Fast Payments System) and international bank cards.
* **Viral Marketing & Growth**:
  * 20% revenue-share referral system with mutual subscription bonus extensions.
  * Instant automated trial periods and custom promo code redemption engine.
* **Integrated Support Desk**:
  * Bi-directional direct customer communication system between users and administrators inside the bot.
* **Infrastructure Reliability**:
  * Systemd service templates, automated SQLite backups, and cron sync timers.

---

## Quickstart

### 1. Clone Repository & Install Dependencies
```bash
git clone https://github.com/sakurawork/truevpn.git /opt/truevpn
cd /opt/truevpn
chmod +x scripts/setup.sh scripts/sync_tunnels.sh
sudo bash scripts/setup.sh
```

### 2. Configure Environment
Create `.env` from the template and configure your credentials:
```bash
cp .env.example .env
nano .env
```

Key configuration parameters:
```ini
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
BOT_USERNAME=TrueVPNBot

BASE_URL=https://vpn.example.com
MINI_APP_URL=https://vpn.example.com/app

CRYPTOPAY_TOKEN=your_cryptobot_token
PLATEGA_KEY=your_platega_secret_key
PLATEGA_MERCHANT_ID=your_platega_merchant_id

SERVER_HOST=your_server_ip
REALITY_DEST=gateway.icloud.com:443
REALITY_SERVER_NAMES=gateway.icloud.com,www.icloud.com
REALITY_PRIVATE_KEY=your_reality_private_key
REALITY_PUBLIC_KEY=your_reality_public_key
```

### 3. Start System Services
```bash
sudo systemctl start truevpn-bot.service
sudo systemctl start truevpn-server.service
sudo systemctl start truevpn-sync.timer
```

Monitor live service logs:
```bash
journalctl -u truevpn-bot.service -f
journalctl -u truevpn-server.service -f
```

---

## Payment Gateways

| Gateway | Supported Currencies & Methods | Verification Mode |
|---|---|---|
| **CryptoBot** | USDT, TON, BTC, ETH, LTC, TRX | Instant Webhook (HMAC SHA-256) |
| **Platega** | SBP (Fast Payments System), Bank Cards | Instant Webhook (Secret API Key) |

---

## Supported Protocols & Client Apps

TrueVPN generates universal Base64 subscription feeds and direct keys compatible with all modern Xray clients:

| Platform | Recommended Applications | Supported Protocols |
|---|---|---|
| **Android** | v2rayNG, Happ, NekoBox | VLESS-Reality, VLESS-WS, gRPC |
| **iOS** | V2Box, Streisand, Happ, FoXray | VLESS-Reality, VLESS-WS, gRPC |
| **Windows** | Hiddify Next, NekoBox, v2rayN | VLESS-Reality, VLESS-WS, gRPC |
| **macOS** | Hiddify Next, V2Box, FoXray | VLESS-Reality, VLESS-WS, gRPC |
| **Linux** | NekoBox, Xray CLI | VLESS-Reality, VLESS-WS, gRPC |

---

## Administration

| Command | Action |
|---|---|
| `/admin`, `/stats` | View active subscribers, total users, daily and monthly revenue analytics |
| `/approve <user_id> <days>` | Manually issue or extend a subscription for a specific user ID |
| `/broadcast <filter> <text>` | Send a targeted mass broadcast (`paid`, `trial`, or `all`) |

---

## Project Structure

```text
├── bot.py                  # Main Telegram bot daemon (Aiogram 3)
├── server.py               # FastAPI backend & subscription endpoint provider
├── tunnel.py               # Xray dynamic configuration & node synchronization engine
├── database.py             # SQLite data layer & automated migrations
├── config.py               # Central environment configuration loader
├── static/
│   └── index.html          # Telegram Mini App client web interface
├── systemd/
│   ├── truevpn-bot.service
│   ├── truevpn-server.service
│   ├── truevpn-sync.service
│   └── truevpn-sync.timer
├── scripts/
│   ├── setup.sh            # Production deployment script
│   └── sync_tunnels.sh     # Synchronization and backup script
├── .env.example            # Environment configuration template
├── requirements.txt        # Python package dependencies
├── LICENSE                 # MIT License
└── README.md               # Documentation
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
