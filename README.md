# TrueVPN ⚡

> **Pro VPN Sales & Automated Subscription Telegram Bot powered by Xray Core (VLESS / Reality / WS)**

TrueVPN is an all-in-one, enterprise-grade Telegram VPN sales and subscription management system. It pairs an asynchronous Aiogram 3 Telegram Bot with a high-throughput FastAPI backend, dynamic Xray tunnel synchronization engine, Telegram Mini App client portal, and multi-currency billing integration (CryptoBot, Platega / SBP, Bank Cards).

---

## 🌟 Key Features

- **🚀 High-Speed Protocols**: Out-of-the-box support for **VLESS + Reality**, **VLESS + WebSocket**, and multi-node dynamic routing.
- **🤖 Modern Telegram Bot**: Built on **Aiogram 3** with interactive inline keyboards, FSM dialogue states, support ticketing, and deep-link attribution.
- **📱 Telegram Mini App Portal**: Sleek, mobile-first Web App allowing clients to view subscription validity, copy configuration keys, and one-click import into client apps.
- **💳 Multi-Gateway Billing**:
  - **CryptoBot** (USDT, TON, BTC, etc. via webhook confirmation).
  - **Platega** (Fast Payment System / SBP & Bank Cards).
- **🎁 Growth & Viral Marketing**:
  - **Referral System**: Generates custom referral links and automatically awards 20% revenue shares and bonus validity days.
  - **Free Trial**: Configurable instant 3-day trial period per new user.
  - **Promo Codes**: Support for customizable promo codes and bonus subscription extensions.
- **🔄 Dynamic Tunnel Synchronizer**: Real-time sync engine that fetches upstream node pools, provisions local inbounds/outbounds, configures Xray routing rules, and auto-reloads services.
- **🛡️ Admin Suite**:
  - Real-time revenue analytics (today, 30 days, all-time).
  - User management & manual subscription issuance (`/approve <user_id> <days>`).
  - Filtered mass broadcasts (`paid`, `trial`, `all`).
  - Bi-directional customer support chat.

---

## 📐 Architecture Overview

```mermaid
flowchart TD
    User([Telegram User]) -->|Interacts| Bot[TrueVPN Bot (Aiogram 3)]
    User -->|Opens Mini App / Sub Link| API[FastAPI Server]
    
    subgraph Core System
        Bot --> DB[(SQLite Database)]
        API --> DB
        SyncWorker[Tunnel Sync Worker] --> DB
        SyncWorker -->|Builds Config| Xray[Xray Core Service]
        SyncWorker -->|Fetches Nodes| Upstream[Upstream Nodes Pool]
    end
    
    subgraph Payment Gateways
        Bot --> CryptoPay[CryptoBot API]
        Bot --> Platega[Platega SBP Gateway]
        CryptoPay -.->|Webhook| API
        Platega -.->|Webhook| API
    end
    
    Xray --> Internet((Encrypted Internet))
```

---

## 📁 Repository Structure

```
truevpn/
├── bot.py                  # Main Aiogram Telegram bot
├── server.py               # FastAPI backend & subscription provider
├── tunnel.py               # Dynamic Xray configuration generator
├── database.py             # SQLite data access layer & migrations
├── config.py               # Central environment configuration
├── static/
│   └── index.html          # Telegram Mini App client interface
├── systemd/
│   ├── truevpn-bot.service
│   ├── truevpn-server.service
│   ├── truevpn-sync.service
│   └── truevpn-sync.timer
├── scripts/
│   ├── setup.sh            # Automated server installer
│   └── sync_tunnels.sh     # Tunnel sync & database backup script
├── .env.example            # Environment configuration template
├── requirements.txt        # Python package dependencies
└── README.md               # Documentation
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- **Ubuntu 22.04+ / Debian 12+**
- **Python 3.10+**
- **Xray-core** installed (`/usr/local/bin/xray`)
- A registered Telegram Bot token from [@BotFather](https://t.me/BotFather)

### 2. Clone the Repository
```bash
git clone https://github.com/sakurawork/truevpn.git /opt/truevpn
cd /opt/truevpn
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
nano .env
```

Key environment options:
```ini
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
BOT_USERNAME=YourVPNBot

BASE_URL=https://vpn.yourdomain.com
MINI_APP_URL=https://vpn.yourdomain.com/app

CRYPTOPAY_TOKEN=your_cryptobot_token
PLATEGA_KEY=your_platega_api_key
PLATEGA_MERCHANT_ID=your_platega_merchant_id

SERVER_HOST=your_server_public_ip
REALITY_DEST=gateway.icloud.com:443
REALITY_SERVER_NAMES=gateway.icloud.com,www.icloud.com
REALITY_PRIVATE_KEY=your_xray_reality_private_key
REALITY_PUBLIC_KEY=your_xray_reality_public_key
```

### 4. Automated Setup
Run the automated installation script to create Python virtual environment and install systemd units:
```bash
chmod +x scripts/setup.sh scripts/sync_tunnels.sh
sudo bash scripts/setup.sh
```

### 5. Start the Services
```bash
sudo systemctl start truevpn-bot.service
sudo systemctl start truevpn-server.service
sudo systemctl start truevpn-sync.timer
```

Check logs:
```bash
journalctl -u truevpn-bot.service -f
journalctl -u truevpn-server.service -f
```

---

## 📲 Client Applications Support

TrueVPN subscription URLs are universally compatible with standard Xray/V2Ray clients:

| Platform | Recommended Client |
| :--- | :--- |
| **Android** | [v2rayNG](https://github.com/2dust/v2rayNG) / [Happ](https://happ.run) |
| **iOS** | [V2Box](https://apps.apple.com/app/v2box-vless-client/id6446814690) / [Streisand](https://apps.apple.com/app/streisand/id6450534064) / [Happ](https://happ.run) |
| **Windows / macOS** | [Hiddify Next](https://github.com/hiddify/hiddify-next) / [NekoBox](https://github.com/MatsuriDayo/nekoray) |

---

## 🔒 Security & Privacy

- Client configurations are deterministically hashed and scoped per user.
- Subscriptions are checked in real-time on every update poll.
- Expired clients are automatically routed to zero-traffic status pages.

---

## 📄 License

This project is licensed under the MIT License.
