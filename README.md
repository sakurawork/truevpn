<div align="center">

# TrueVPN

### Professional Telegram Bot & Management Panel for Automated VPN Sales and Subscriptions

<p>
  <a href="https://github.com/sakurawork/truevpn/stargazers">
    <img src="https://img.shields.io/github/stars/sakurawork/truevpn?style=flat-square&color=blue" alt="Stars"/>
  </a>
  <a href="https://github.com/sakurawork/truevpn/network/members">
    <img src="https://img.shields.io/github/forks/sakurawork/truevpn?style=flat-square" alt="Forks"/>
  </a>
  <a href="https://github.com/sakurawork/truevpn/issues">
    <img src="https://img.shields.io/github/issues/sakurawork/truevpn?style=flat-square" alt="Issues"/>
  </a>
  <a href="https://github.com/sakurawork/truevpn/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/sakurawork/truevpn?style=flat-square" alt="License"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Aiogram-3.4+-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="Aiogram 3"/>
  <img src="https://img.shields.io/badge/Xray-Core-1.8+-black?style=flat-square" alt="Xray Core"/>
</p>

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Payment Gateways](#payment-gateways)
- [Supported Protocols & Clients](#supported-protocols--clients)
- [Installation & Deployment](#installation--deployment)
  - [Prerequisites](#prerequisites)
  - [Quick Setup](#quick-setup)
  - [Configuration](#configuration)
  - [Systemd Services](#systemd-services)
- [Admin Commands](#admin-commands)
- [Project Layout](#project-layout)
- [License](#license)

---

## Overview

TrueVPN is a production-ready, automated Telegram VPN sales bot and subscription provisioning platform powered by Xray Core.

It provides end-to-end automation for selling VPN services: client onboarding, automated payments, dynamic VLESS and Reality configuration generation, real-time node synchronization, user-friendly Telegram Mini App portal, referral revenue sharing, and administrative control.

---

## Key Features

- **Automated Provisioning**: Generates individual, cryptographic client credentials upon payment or trial activation.
- **Dynamic Node Synchronization**: Automatically pulls upstream server pools and compiles local routing rules, inbounds, and outbounds for Xray.
- **Telegram Mini App**: Built-in responsive Web App client portal for checking validity, browsing nodes, and one-tap import into VPN apps.
- **Multi-Gateway Billing**: Native support for CryptoBot (USDT/crypto) and Platega (SBP / Bank Cards) with automated instant webhook confirmations.
- **Growth & Marketing**:
  - Multi-tier referral system with 20% revenue rewards and mutual subscription bonus days.
  - Automated free trial period (configurable duration).
  - Promo code redemption engine.
- **Customer Support Integration**: Direct bi-directional messaging between users and administrators inside the bot.
- **Operational Reliability**: Background systemd services, automated SQLite backups, and cron sync timers.

---

## Architecture

```mermaid
flowchart TD
    User([Telegram User]) -->|Commands & WebApp| Bot[Telegram Bot (Aiogram 3)]
    User -->|Subscription Link / WebApp| API[FastAPI Backend]
    
    subgraph Core
        Bot --> DB[(SQLite Database)]
        API --> DB
        SyncWorker[Tunnel Sync Worker] --> DB
        SyncWorker -->|Builds Config| Xray[Xray Core Service]
        SyncWorker -->|Fetches Upstream Nodes| Upstream[Node Pool]
    end
    
    subgraph Gateways
        Bot --> CryptoPay[CryptoBot API]
        Bot --> Platega[Platega Gateway]
        CryptoPay -.->|Webhook| API
        Platega -.->|Webhook| API
    end
    
    Xray --> Internet((Encrypted Traffic))
```

---

## Payment Gateways

| Gateway | Supported Methods | Confirmation Mode |
| :--- | :--- | :--- |
| **CryptoBot** | USDT, TON, BTC, ETH, LTC, and more | Instant Webhook (HMAC verified) |
| **Platega** | SBP (Fast Payments System), Russian & International Bank Cards | Instant Webhook (API Key verified) |

---

## Supported Protocols & Clients

TrueVPN generates universal Base64 subscription links compatible with all modern Xray-based client applications.

### Protocols
- VLESS + Reality (XTLS-Vision)
- VLESS + WebSocket
- VLESS + gRPC / XHTTP

### Client Applications

| Platform | Recommended Clients |
| :--- | :--- |
| **Android** | v2rayNG, Happ, NekoBox |
| **iOS** | V2Box, Streisand, Happ, FoXray |
| **Windows** | Hiddify Next, NekoBox, v2rayN |
| **macOS** | Hiddify Next, V2Box, FoXray |
| **Linux** | NekoBox, Xray CLI |

---

## Installation & Deployment

### Prerequisites

- OS: Ubuntu 22.04 LTS or Debian 12
- Python: 3.10 or higher
- Xray Core installed (`/usr/local/bin/xray`)
- Domain with SSL certificate (for webhook endpoints and Telegram Mini App)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Quick Setup

1. Clone the repository:
```bash
git clone https://github.com/sakurawork/truevpn.git /opt/truevpn
cd /opt/truevpn
```

2. Run the automated installer:
```bash
chmod +x scripts/setup.sh scripts/sync_tunnels.sh
sudo bash scripts/setup.sh
```

### Configuration

Create `.env` from the example template and fill in your parameters:
```bash
cp .env.example .env
nano .env
```

Environment variables reference:

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

### Systemd Services

The installation script configures three systemd units:

- `truevpn-bot.service`: Runs the Telegram bot daemon.
- `truevpn-server.service`: Runs the FastAPI subscription & webhook server.
- `truevpn-sync.timer`: Triggers hourly tunnel synchronization and database backup.

To control the services:
```bash
systemctl start truevpn-bot.service
systemctl start truevpn-server.service
systemctl start truevpn-sync.timer
```

To view real-time logs:
```bash
journalctl -u truevpn-bot.service -f
journalctl -u truevpn-server.service -f
```

---

## Admin Commands

| Command | Description |
| :--- | :--- |
| `/admin`, `/stats` | View active subscribers, total users, daily and monthly revenue metrics |
| `/approve <user_id> <days>` | Manually issue or extend a subscription for a specified user |
| `/broadcast <filter> <text>` | Send a targeted mass broadcast (`paid`, `trial`, or `all`) |

---

## Project Layout

```
truevpn/
├── bot.py                  # Telegram bot implementation (Aiogram 3)
├── server.py               # FastAPI backend & subscription endpoint provider
├── tunnel.py               # Xray dynamic configuration & node synchronization engine
├── database.py             # SQLite database layer & schema migrations
├── config.py               # Environment configuration loader
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
└── README.md               # Documentation
```

---

## License

This project is licensed under the MIT License.
