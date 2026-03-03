import asyncio
import aiohttp
import base64
import json
from datetime import datetime
import os
import time

SS_LIST_FILE = "sslist.txt"

OUTPUT_TEXT = "Molestunnels.txt"
OUTPUT_BASE64 = "Molestunnels_base64.txt"

TIMEOUT = 8
CONCURRENCY = 50

STATIC_LINES = [
    "#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
    "#profile-update-interval: 1",
    "#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]

# ================= ЗАГРУЗКА =================

async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=TIMEOUT) as resp:
            return await resp.text()
    except:
        return None


def decode_if_base64(text):
    try:
        padded = text.strip() + "=" * (-len(text.strip()) % 4)
        decoded = base64.b64decode(padded).decode()
        if "vless://" in decoded or "vmess://" in decoded:
            return decoded
        return text
    except:
        return text


def extract_keys(text):
    lines = text.splitlines()
    keys = []
    for line in lines:
        line = line.strip()
        if line.startswith("vless://") or line.startswith("vmess://"):
            keys.append(line)
    return keys


# ================= HOST / PORT =================

def extract_host_port(key):
    try:
        if key.startswith("vless://"):
            part = key.split("@")[1]
            host_port = part.split("?")[0]
            host, port = host_port.split(":")
            return host, int(port)

        if key.startswith("vmess://"):
            raw = key.replace("vmess://", "")
            padded = raw + "=" * (-len(raw) % 4)
            data = json.loads(base64.b64decode(padded).decode())
            host = data.get("add")
            port = int(data.get("port"))
            return host, port

    except:
        return None, None


# ================= TCP ПРОВЕРКА =================

async def check_tcp(host, port):
    try:
        start = time.perf_counter()

        conn = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(conn, timeout=TIMEOUT)

        latency = (time.perf_counter() - start) * 1000

        writer.close()
        await writer.wait_closed()

        return True, round(latency, 1)

    except:
        return False, None


# ================= HTTP ПРОВЕРКА =================

async def check_http(host, port):
    try:
        scheme = "http"
        if port == 443:
            scheme = "https"

        url = f"{scheme}://{host}"

        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url) as resp:
                return resp.status < 500

    except:
        return False


# ================= ВАЛИДАЦИЯ =================

async def validate(key):
    host, port = extract_host_port(key)

    if not host or not port:
        return None

    # 1. TCP проверка (обязательная)
    tcp_ok, latency = await check_tcp(host, port)

    if not tcp_ok:
        return None

    # 2. HTTP/HTTPS проверка (дополнительная)
    http_ok = True

    if port in (80, 443):
        http_ok = await check_http(host, port)

    if not http_ok:
        return None

    return key, latency


# ================= MAIN =================

async def main():

    if not os.path.exists(SS_LIST_FILE):
        print("sslist.txt не найден.")
        return

    with open(SS_LIST_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        texts = await asyncio.gather(*[fetch_text(session, url) for url in urls])

    all_keys = []

    for text in texts:
        if not text:
            continue
        text = decode_if_base64(text)
        all_keys.extend(extract_keys(text))

    # антидубликат
    all_keys = list(dict.fromkeys(all_keys))

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def sem_task(k):
        async with semaphore:
            return await validate(k)

    results = await asyncio.gather(*[sem_task(k) for k in all_keys])

    valid = [r for r in results if r]

    # сортировка по latency
    valid.sort(key=lambda x: x[1])

    today = datetime.now().strftime("%d-%m-%Y")

    renamed = []

    for i, (key, latency) in enumerate(valid, 1):
        name = f"СЕРВЕР {i:04d} | {latency}ms | ОБНОВЛЕН {today}"
        if "#" in key:
            key = key.split("#")[0]
        renamed.append(key + "#" + name)

    announce = f"#announce: АКТИВНЫХ СЕРВЕРОВ {len(renamed)} | ОБНОВЛЕНО {today}"

    final_lines = []
    final_lines.extend(STATIC_LINES)
    final_lines.append(announce)
    final_lines.extend(renamed)

    final_text = "\n".join(final_lines)

    with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(final_text)

    encoded = base64.b64encode(final_text.encode()).decode()

    with open(OUTPUT_BASE64, "w", encoding="utf-8") as f:
        f.write(encoded)

    print("Обновлены Molestunnels.txt и Molestunnels_base64.txt")
    print(f"Активных серверов: {len(renamed)}")


if __name__ == "__main__":
    asyncio.run(main())
