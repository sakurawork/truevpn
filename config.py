import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

CRYPTOPAY_TOKEN = os.getenv("CRYPTOPAY_TOKEN", "")
PLATEGA_KEY = os.getenv("PLATEGA_KEY", "")
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")

BASE_URL = os.getenv("BASE_URL", "https://example.com").rstrip("/")
MINI_APP_URL = os.getenv("MINI_APP_URL", f"{BASE_URL}/app")
BOT_USERNAME = os.getenv("BOT_USERNAME", "TrueVPNBot")

DB_PATH = os.getenv("DB_PATH", "database.db")
SUBSCRIPTION_CACHE_PATH = os.getenv("SUBSCRIPTION_CACHE_PATH", "subscription_cache.json")
TUNNELS_METADATA = os.getenv("TUNNELS_METADATA", "/usr/local/etc/xray/tunnels_metadata.json")

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")
REQUIRED_CHANNEL_LINK = os.getenv("REQUIRED_CHANNEL_LINK", "")

XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")
XRAY_CONFIG_BACKUP = os.getenv("XRAY_CONFIG_BACKUP", "/usr/local/etc/xray/config.json.orig")
UPSTREAM_SUB_URL = os.getenv("UPSTREAM_SUB_URL", "")
TUNNEL_START_PORT = int(os.getenv("TUNNEL_START_PORT", "10001"))
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")

REALITY_DEST = os.getenv("REALITY_DEST", "gateway.icloud.com:443")
REALITY_SERVER_NAMES = [s.strip() for s in os.getenv("REALITY_SERVER_NAMES", "gateway.icloud.com,www.icloud.com").split(",") if s.strip()]
REALITY_PRIVATE_KEY = os.getenv("REALITY_PRIVATE_KEY", "")
REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY", "")
REALITY_SHORT_IDS = [s.strip() for s in os.getenv("REALITY_SHORT_IDS", "e39882243b75ee58,61ca73438282d387").split(",") if s.strip()]

API_PORT = int(os.getenv("API_PORT", "8000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
