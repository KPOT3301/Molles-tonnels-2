import asyncio
import aiohttp
import base64
import json
import ssl
import time
from datetime import datetime
import os

SS_LIST_FILE = "sslist.txt"

OUTPUT_TEXT = "Molestunnels.txt"
OUTPUT_BASE64 = "Molestunnels_base64.txt"

TIMEOUT = 6
CONCURRENCY = 100
RETRY_COUNT = 3
MAX_LATENCY = 2.5  # максимум 2.5 секунды

BAD_PORTS = {80, 8080, 8880}

STATIC_LINES = [
"#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#profile-update-interval: 1",
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
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(("vless://", "vmess://"))
    ]


# ================= ПАРСИНГ =================

def parse_vless(key):
    try:
        part = key.split("@")[1]
        host_port = part.split("?")[0]
        host, port = host_port.split(":")
        tls = "security=tls" in key
        ws = "type=ws" in key
        return host, int(port), tls, ws
    except:
        return None


def parse_vmess(key):
    try:
        raw = key.replace("vmess://", "")
        padded = raw + "=" * (-len(raw) % 4)
        data = json.loads(base64.b64decode(padded).decode())
        host = data.get("add")
        port = int(data.get("port"))
        tls = data.get("tls") == "tls"
        ws = data.get("net") == "ws"
        return host, port, tls, ws
    except:
        return None


def parse_key(key):
    if key.startswith("vless://"):
        return parse_vless(key)
    if key.startswith("vmess://"):
        return parse_vmess(key)
    return None


# ================= ПРОВЕРКИ =================

async def tcp_check(host, port, use_tls):
    try:
        ssl_context = None
        if use_tls:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        start = time.time()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=TIMEOUT
        )

        latency = time.time() - start

        writer.close()
        await writer.wait_closed()

        return True, latency

    except:
        return False, None


async def ws_check(host, port, use_tls):
    scheme = "wss" if use_tls else "ws"
    url = f"{scheme}://{host}:{port}/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, timeout=TIMEOUT):
                return True
    except:
        return False


async def validate(key):
    parsed = parse_key(key)
    if not parsed:
        return None

    host, port, use_tls, use_ws = parsed

    if port in BAD_PORTS:
        return None

    success = 0
    best_latency = 999

    for _ in range(RETRY_COUNT):
        ok, latency = await tcp_check(host, port, use_tls)
        if ok:
            success += 1
            best_latency = min(best_latency, latency)

        await asyncio.sleep(0.3)

    if success < 2:
        return None

    if best_latency > MAX_LATENCY:
        return None

    if use_ws:
        if not await ws_check(host, port, use_tls):
            return None

    return key, best_latency


# ================= MAIN =================

async def main():

    if not os.path.exists(SS_LIST_FILE):
        print("sslist.txt не найден.")
        return

    with open(SS_LIST_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        texts = await asyncio.gather(*[fetch_text(session, url) for url in urls])

    all_keys = []
    for text in texts:
        if text:
            text = decode_if_base64(text)
            all_keys.extend(extract_keys(text))

    all_keys = list(dict.fromkeys(all_keys))

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def sem_task(k):
        async with semaphore:
            return await validate(k)

    results = await asyncio.gather(*[sem_task(k) for k in all_keys])

    valid = [r for r in results if r]

    # сортировка по пингу
    valid.sort(key=lambda x: x[1])

    today = datetime.now().strftime("%d-%m-%Y")

    final_keys = []
    for i, (key, latency) in enumerate(valid, 1):
        name = f"СЕРВЕР {i:04d} | {latency:.2f}s | {today}"
        if "#" in key:
            key = key.split("#")[0]
        final_keys.append(key + "#" + name)

    announce = f"#announce: АКТИВНЫХ {len(final_keys)} | {today}"

    final_lines = []
    final_lines.extend(STATIC_LINES)
    final_lines.append(announce)
    final_lines.extend(final_keys)

    final_text = "\n".join(final_lines)

    with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(final_text)

    encoded = base64.b64encode(final_text.encode()).decode()
    with open(OUTPUT_BASE64, "w", encoding="utf-8") as f:
        f.write(encoded)

    print(f"Готово. Рабочих серверов: {len(final_keys)}")


if __name__ == "__main__":
    asyncio.run(main())
    
