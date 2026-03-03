import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests

TIMEOUT = 5
XRAY_PATH = "./xray"
TEST_URL = "https://www.google.com"


# ================= TCP CHECK =================
async def tcp_check(host, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


# ================= VLESS PARSER =================
def parse_vless(link):
    parsed = urlparse(link)

    params = parse_qs(parsed.query)

    def get(key, default=None):
        return params.get(key, [default])[0]

    return {
        "uuid": parsed.username,
        "host": parsed.hostname,
        "port": parsed.port,
        "type": get("type", "tcp"),
        "security": get("security", "none"),
        "sni": get("sni"),
        "path": get("path", ""),
        "host_header": get("host"),
        "serviceName": get("serviceName"),
        "flow": get("flow"),
        "pbk": get("pbk"),
        "sid": get("sid"),
    }


# ================= XRAY CONFIG =================
def build_config(data):
    stream = {
        "network": data["type"],
        "security": data["security"],
    }

    if data["security"] == "tls":
        stream["tlsSettings"] = {
            "serverName": data["sni"] or data["host"]
        }

    if data["security"] == "reality":
        stream["realitySettings"] = {
            "serverName": data["sni"],
            "publicKey": data["pbk"],
            "shortId": data["sid"] or ""
        }

    if data["type"] == "ws":
        stream["wsSettings"] = {
            "path": data["path"],
            "headers": {"Host": data["host_header"]} if data["host_header"] else {}
        }

    if data["type"] == "grpc":
        stream["grpcSettings"] = {
            "serviceName": data["serviceName"]
        }

    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": data["host"],
                "port": int(data["port"]),
                "users": [{
                    "id": data["uuid"],
                    "encryption": "none",
                    "flow": data["flow"]
                }]
            }]
        },
        "streamSettings": stream
    }

    return {
        "inbounds": [{
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [outbound]
    }


# ================= XRAY CHECK =================
def xray_check(link):
    try:
        data = parse_vless(link)
        config = build_config(data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(json.dumps(config).encode())
            tmp_path = tmp.name

        proc = subprocess.Popen(
            [XRAY_PATH, "-config", tmp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(2)

        proxies = {
            "http": "socks5h://127.0.0.1:10808",
            "https": "socks5h://127.0.0.1:10808",
        }

        try:
            r = requests.get(TEST_URL, proxies=proxies, timeout=8)
            ok = r.status_code == 200
        except:
            ok = False

        proc.kill()
        os.remove(tmp_path)

        return ok

    except:
        return False


# ================= FULL CHECK =================
async def check_vless(link):
    try:
        data = parse_vless(link)

        tcp_ok = await tcp_check(data["host"], data["port"])
        if not tcp_ok:
            return False

        return xray_check(link)

    except:
        return False


async def process_links(links):
    tasks = [check_vless(link) for link in links]
    results = await asyncio.gather(*tasks)

    alive = []
    for link, ok in zip(links, results):
        if ok:
            alive.append(link)

    return alive


# ================= FILE WRITER =================
def write_files(alive):
    moscow = datetime.now(ZoneInfo("Europe/Moscow"))
    date_str = moscow.strftime("%d-%m-%Y")

    announce = f"#announce: 🚀 РАБОЧИХ {len(alive)} | 📅 {date_str}"

    with open("Molestunnels.txt", "w", encoding="utf-8") as f:
        f.write(announce + "\n")
        for link in alive:
            f.write(link + "\n")

    encoded = base64.b64encode(
        ("\n".join([announce] + alive)).encode()
    ).decode()

    with open("Molestunnels_base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)


# ================= MAIN =================
async def main():
    with open("sslist.txt", "r", encoding="utf-8") as f:
        links = [l.strip() for l in f if l.startswith("vless://")]

    alive = await process_links(links)
    write_files(alive)


if __name__ == "__main__":
    asyncio.run(main())
