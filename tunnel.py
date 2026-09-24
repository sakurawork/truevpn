import urllib.request
import urllib.parse
import json
import base64
import re
import os
import subprocess
import sys
import ssl
import socket
import hashlib
import sqlite3
import time
import uuid

from config import (
    XRAY_CONFIG_PATH,
    XRAY_CONFIG_BACKUP,
    UPSTREAM_SUB_URL,
    TUNNEL_START_PORT,
    SERVER_HOST,
    DB_PATH,
    REALITY_DEST,
    REALITY_SERVER_NAMES,
    REALITY_PRIVATE_KEY,
    REALITY_PUBLIC_KEY,
    REALITY_SHORT_IDS,
    TUNNELS_METADATA,
    SUBSCRIPTION_CACHE_PATH,
)

def generate_deterministic_uuid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

def load_active_user_clients():
    clients = []
    if not os.path.exists(DB_PATH):
        return [{"id": str(uuid.uuid4()), "flow": "xtls-rprx-vision", "email": "default_user@truevpn"}]
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = int(time.time())
        c.execute("SELECT user_id, uuid, sub_expire_at, is_blocked FROM users WHERE sub_expire_at > ? AND is_blocked = 0", (now,))
        rows = c.fetchall()
        for r in rows:
            uid, u_uuid, exp, blk = r
            if not u_uuid:
                u_uuid = generate_deterministic_uuid(f"user_{uid}")
                c.execute("UPDATE users SET uuid = ? WHERE user_id = ?", (u_uuid, uid))
                conn.commit()
            clients.append({
                "id": u_uuid,
                "flow": "xtls-rprx-vision",
                "email": f"user_{uid}@truevpn"
            })
        conn.close()
    except Exception as e:
        print(f"[-] Error loading active users: {e}")
        
    if not clients:
        clients.append({"id": str(uuid.uuid4()), "flow": "xtls-rprx-vision", "email": "fallback@truevpn"})
    return clients

def parse_vless(link):
    try:
        if not link.startswith("vless://"):
            return None
        parts = link[8:].split("@")
        uuid_str = parts[0]
        rest = parts[1]
        
        host_port_query = rest.split("#")
        tag = urllib.parse.unquote(host_port_query[1]) if len(host_port_query) > 1 else "Unknown"
        
        hp_query = host_port_query[0].split("?")
        host_port = hp_query[0].split(":")
        host = host_port[0]
        port = int(host_port[1])
        
        query_params = urllib.parse.parse_qs(hp_query[1]) if len(hp_query) > 1 else {}
        params = {k: v[0] for k, v in query_params.items()}
        
        return {
            "uuid": uuid_str,
            "host": host,
            "port": port,
            "tag": tag,
            "params": params,
            "raw": link
        }
    except Exception as e:
        print(f"[-] Error parsing link: {e}")
        return None

def fetch_subscription_links():
    if not UPSTREAM_SUB_URL:
        if os.path.exists(SUBSCRIPTION_CACHE_PATH):
            try:
                with open(SUBSCRIPTION_CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [loc["key"] for loc in data.get("locations", []) if "key" in loc]
            except Exception:
                pass
        return []
    try:
        req = urllib.request.Request(
            UPSTREAM_SUB_URL,
            headers={"User-Agent": "v2rayNG/1.8.5"}
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore").strip()
            
        try:
            data = json.loads(content)
            if "locations" in data:
                with open(SUBSCRIPTION_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return [loc["key"] for loc in data.get("locations", []) if "key" in loc]
        except Exception:
            pass

        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
            links = [l.strip() for l in decoded.splitlines() if l.strip().startswith("vless://")]
            if links:
                return links
        except Exception:
            pass

        links = [l.strip() for l in content.splitlines() if l.strip().startswith("vless://")]
        return links
    except Exception as e:
        print(f"[-] Error fetching subscription: {e}")
        if os.path.exists(SUBSCRIPTION_CACHE_PATH):
            try:
                with open(SUBSCRIPTION_CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [loc["key"] for loc in data.get("locations", []) if "key" in loc]
            except Exception:
                pass
        return []

def get_tls_cert_sha256(host, port, server_name):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=server_name) as ssock:
                cert_bin = ssock.getpeercert(binary_form=True)
                return hashlib.sha256(cert_bin).hexdigest()
    except Exception as e:
        print(f"[-] Failed to get cert hash for {server_name} ({host}:{port}): {e}")
        return None

def generate_xray_config(parsed_tunnels):
    active_clients = load_active_user_clients()
    inbounds = []
    outbounds = []
    rules = []
    metadata = []

    inbound_reality = {
        "listen": "0.0.0.0",
        "port": 8443,
        "protocol": "vless",
        "settings": {
            "clients": active_clients,
            "decryption": "none"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "show": False,
                "dest": REALITY_DEST,
                "xver": 0,
                "serverNames": REALITY_SERVER_NAMES,
                "privateKey": REALITY_PRIVATE_KEY,
                "shortIds": REALITY_SHORT_IDS
            }
        },
        "tag": "inbound-reality"
    }
    inbounds.append(inbound_reality)

    ws_clients = []
    for cl in active_clients:
        ws_cl = dict(cl)
        ws_cl.pop("flow", None)
        ws_clients.append(ws_cl)

    for idx, t in enumerate(parsed_tunnels):
        port = TUNNEL_START_PORT + idx
        in_tag = f"inbound-tunnel-{idx}"
        out_tag = f"outbound-tunnel-{idx}"
        ws_path = f"/tunnel-{idx}-ws"
        clean_name = t["tag"].strip()
        
        inbounds.append({
            "listen": "0.0.0.0",
            "port": port,
            "protocol": "vless",
            "settings": {
                "clients": ws_clients,
                "decryption": "none"
            },
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": ws_path
                }
            },
            "tag": in_tag
        })

        params = t["params"]
        net_type = params.get("type", "tcp")
        security = params.get("security", "none")
        
        out_stream = {
            "network": net_type,
            "security": security
        }

        if security == "tls":
            tls_settings = {
                "allowInsecure": True,
                "serverName": params.get("sni", t["host"])
            }
            if "alpn" in params:
                tls_settings["alpn"] = params["alpn"].split(",")
            out_stream["tlsSettings"] = tls_settings
        elif security == "reality":
            reality_settings = {
                "show": False,
                "fingerprint": params.get("fp", "chrome"),
                "serverName": params.get("sni", t["host"]),
                "publicKey": params.get("pbk", ""),
                "shortId": params.get("sid", ""),
                "spiderX": params.get("spx", "/")
            }
            out_stream["realitySettings"] = reality_settings

        if net_type == "ws":
            out_stream["wsSettings"] = {
                "path": params.get("path", "/"),
                "headers": {
                    "Host": params.get("host", params.get("sni", t["host"]))
                }
            }
        elif net_type == "grpc":
            out_stream["grpcSettings"] = {
                "serviceName": params.get("serviceName", "")
            }
        elif net_type == "xhttp":
            out_stream["xhttpSettings"] = {
                "path": params.get("path", "/"),
                "host": params.get("host", params.get("sni", t["host"])),
                "mode": params.get("mode", "auto")
            }

        vnext_user = {
            "id": t["uuid"],
            "encryption": params.get("encryption", "none")
        }
        if "flow" in params and params["flow"]:
            vnext_user["flow"] = params["flow"]

        outbounds.append({
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": t["host"],
                    "port": t["port"],
                    "users": [vnext_user]
                }]
            },
            "streamSettings": out_stream,
            "tag": out_tag
        })

        rules.append({
            "type": "field",
            "inboundTag": [in_tag],
            "outboundTag": out_tag
        })

        metadata.append({
            "index": idx,
            "name": clean_name,
            "port": port,
            "path": ws_path,
            "target_host": t["host"],
            "target_port": t["port"]
        })

    outbounds.append({"protocol": "freedom", "tag": "direct"})
    outbounds.append({"protocol": "blackhole", "tag": "block"})

    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "AsIs",
            "rules": rules
        }
    }
    return config, metadata

def test_and_apply_config(config, metadata):
    tmp_config = "/tmp/xray_truevpn_test.json"
    with open(tmp_config, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    cmd = ["xray", "run", "-test", "-config", tmp_config]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            print(f"[-] Xray config test failed: {res.stderr}")
            return False
    except Exception as e:
        print(f"[-] Warning: could not test config with xray: {e}")

    try:
        os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
        with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
        os.makedirs(os.path.dirname(TUNNELS_METADATA), exist_ok=True)
        with open(TUNNELS_METADATA, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        subprocess.run(["systemctl", "restart", "xray"], check=False)
        print("[+] Xray config applied and service restarted successfully.")
        return True
    except Exception as e:
        print(f"[-] Error applying config: {e}")
        return False

def main():
    print("[*] Fetching subscription links...")
    links = fetch_subscription_links()
    if not links:
        print("[-] No upstream links found.")
        sys.exit(1)
        
    parsed = []
    for l in links:
        item = parse_vless(l)
        if item:
            parsed.append(item)
            
    print(f"[+] Parsed {len(parsed)} tunnels.")
    config, metadata = generate_xray_config(parsed)
    success = test_and_apply_config(config, metadata)
    if success:
        print(f"[+] Successfully synchronized {len(parsed)} tunnels.")
    else:
        print("[-] Synchronization failed.")

if __name__ == "__main__":
    main()
