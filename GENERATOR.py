import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlunparse
from zoneinfo import ZoneInfo

import requests

XRAY_PATH = "./xray"
MAX_WORKERS = 20
TIMEOUT = 3


# ================= 5 СТАТИЧНЫХ СТРОК =================
STATIC_LINES = [
    "#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
    "#profile-update-interval: 1",
    "#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]


# ================= DOWNLOAD =================
def download_subscriptions():
    if not os.path.exists("sslist.txt"):
        return []

    with open("sslist.txt", "r", encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.startswith("http")]

    all_links = []

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            content = r.text.strip()

            try:
                decoded = base64.b64decode(content).decode("utf-8")
                content = decoded
            except:
                pass

            for line in content.splitlines():
                if line.startswith("vless://"):
                    all_links.append(line.strip())

        except:
            continue

    return list(set(all_links))


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
        "network": get("type", "tcp"),
        "security": get("security", "none"),
        "sni": get("sni"),
        "path": get("path", ""),
        "host_header": get("host"),
        "serviceName": get("serviceName"),
        "flow": get("flow"),
        "pbk": get("pbk"),
        "sid": get("sid"),
    }


def build_config(data):
    stream = {"network": data["network"], "security": data["security"]}

    if data["security"] == "tls":
        stream["tlsSettings"] = {"serverName": data["sni"] or data["host"]}

    if data["security"] == "reality":
        stream["realitySettings"] = {
            "serverName": data["sni"],
            "publicKey": data["pbk"],
            "shortId": data["sid"] or ""
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
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "socks"
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
            config_path = tmp.name

        proc = subprocess.Popen(
            [XRAY_PATH, "-config", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        time.sleep(TIMEOUT)
        alive = proc.poll() is None

        proc.kill()
        os.remove(config_path)

        return alive

    except:
        return False


async def bounded_check(sem, link):
    async with sem:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, xray_check, link)


# ================= MAIN =================
async def main():
    links = download_subscriptions()
    print("Найдено:", len(links))

    sem = asyncio.Semaphore(MAX_WORKERS)
    tasks = [bounded_check(sem, link) for link in links]
    results = await asyncio.gather(*tasks)

    alive_links = [l for l, ok in zip(links, results) if ok]
    print("Рабочих:", len(alive_links))

    write_files(alive_links)


# ================= WRITE FILE =================
def rename_link(link, index, date_str):
    parsed = urlparse(link)
    new_name = f"СЕРВЕР {index:04d}| ОБНОВЛЕН {date_str}"
    return urlunparse(parsed._replace(fragment=new_name))


def write_files(alive_links):
    moscow = datetime.now(ZoneInfo("Europe/Moscow"))
    date_str = moscow.strftime("%d-%m-%Y")

    renamed = [
        rename_link(link, i + 1, date_str)
        for i, link in enumerate(alive_links)
    ]

    announce = f"#announce: 🚀 АКТИВНЫХ {len(renamed)} | 📅 {date_str}"

    lines = STATIC_LINES + [announce] + renamed

    with open("Molestunnels.txt", "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    encoded = base64.b64encode("\n".join(lines).encode()).decode()

    with open("Molestunnels_base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)


if __name__ == "__main__":
    asyncio.run(main())
