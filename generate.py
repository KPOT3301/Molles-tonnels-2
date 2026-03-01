import asyncio
import aiohttp
import base64
import re
import socket
import subprocess
import json
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

INPUT_FILE = "sources.txt"
OUTPUT_FILE = "Molestunnels.txt"
MAX_SERVERS = 1000
MAX_PING = 1000
PING_CONCURRENCY = 200

HEADER = """#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
"""

# ===== ФЛАГИ СТРАН =====
FLAG_MAP = {
    "RU": "🇷🇺 Россия",
    "DE": "🇩🇪 Германия",
    "NL": "🇳🇱 Нидерланды",
    "US": "🇺🇸 США",
    "FR": "🇫🇷 Франция",
    "GB": "🇬🇧 Великобритания",
    "FI": "🇫🇮 Финляндия",
    "PL": "🇵🇱 Польша",
    "TR": "🇹🇷 Турция",
    "KZ": "🇰🇿 Казахстан",
    "JP": "🇯🇵 Япония",
    "SG": "🇸🇬 Сингапур",
}

# ===== Загрузка ссылок =====
async def fetch(session, url):
    try:
        async with session.get(url, timeout=15) as resp:
            return await resp.text()
    except:
        return ""

async def load_sources():
    if not os.path.exists(INPUT_FILE):
        return []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    keys = []
    for data in results:
        if not data:
            continue
        try:
            decoded = base64.b64decode(data).decode()
        except:
            decoded = data
        keys.extend(decoded.splitlines())

    return keys

# ===== Парсинг VLESS =====
def parse_vless(line):
    if not line.startswith("vless://"):
        return None
    try:
        parsed = urlparse(line)
        host = parsed.hostname
        port = parsed.port
        return host, port
    except:
        return None

# ===== Пинг =====
async def ping(host):
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()

        match = re.search(r'time=(\d+\.?\d*)', output)
        if match:
            return float(match.group(1))
    except:
        pass
    return None

# ===== Проверка выхода в интернет через Xray =====
async def check_google(vless_key):
    config = {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": parse_vless(vless_key)[0],
                    "port": parse_vless(vless_key)[1],
                    "users": [{
                        "id": vless_key.split("://")[1].split("@")[0],
                        "encryption": "none"
                    }]
                }]
            },
            "streamSettings": {"network": "tcp"}
        }]
    }

    with open("test.json", "w") as f:
        json.dump(config, f)

    proc = await asyncio.create_subprocess_exec(
        "./xray", "-config", "test.json",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )

    await asyncio.sleep(2)

    try:
        test = await asyncio.create_subprocess_exec(
            "curl", "--socks5", "127.0.0.1:10808",
            "--max-time", "5",
            "https://www.google.com",
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await test.communicate()
        success = b"html" in stdout.lower()
    except:
        success = False

    proc.kill()
    await proc.wait()

    return success

# ===== Основная логика =====
async def main():
    print("Загрузка ключей...")
    keys = await load_sources()

    keys = list(set([k.strip() for k in keys if k.startswith("vless://")]))

    print(f"Найдено VLESS: {len(keys)}")

    valid = []
    semaphore = asyncio.Semaphore(PING_CONCURRENCY)

    async def check_key(key):
        async with semaphore:
            parsed = parse_vless(key)
            if not parsed:
                return None

            host, port = parsed
            ping_time = await ping(host)
            if ping_time and ping_time <= MAX_PING:
                if await check_google(key):
                    return (key, ping_time)
        return None

    tasks = [check_key(k) for k in keys]
    for future in asyncio.as_completed(tasks):
        result = await future
        if result:
            valid.append(result)
            if len(valid) >= MAX_SERVERS:
                break

    valid.sort(key=lambda x: x[1])
    valid = valid[:MAX_SERVERS]

    print(f"Отобрано серверов: {len(valid)}")

    # ===== Формирование итогового файла =====
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER)

        for i, (key, ping_time) in enumerate(valid, 1):
            country_code = key.upper().split("#")[-1][:2]
            country = FLAG_MAP.get(country_code, "🌍 Unknown")
            name = f"KPOT-{i:04d} | {country} | {int(ping_time)}ms"
            if "#" in key:
                key = key.split("#")[0]
            f.write(f"{key}#{name}\n")

if __name__ == "__main__":
    asyncio.run(main())
