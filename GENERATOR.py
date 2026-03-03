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

TIMEOUT = 6
CONCURRENCY = 20
MIN_SCORE = 60

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


# ================= ИЗВЛЕЧЕНИЕ HOST/PORT =================

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
            return data.get("add"), int(data.get("port"))
    except:
        return None, None


# ================= ПРОВЕРКА =================

async def check_tcp(host, port):
    try:
        start = time.perf_counter()
        reader, writer = await asyncio.open_connection(host, port)
        latency = time.perf_counter() - start
        writer.close()
        await writer.wait_closed()
        return latency
    except:
        return None


def calculate_score(latency):
    if latency is None:
        return 0

    score = 50  # TCP открыт

    if latency < 0.4:
        score += 40
    elif latency < 0.8:
        score += 30
    elif latency < 1.2:
        score += 20
    elif latency < 1.8:
        score += 10

    return score


async def validate(key, semaphore):
    host, port = extract_host_port(key)
    if not host or not port:
        return None

    async with semaphore:
        latency = await check_tcp(host, port)

    score = calculate_score(latency)

    if score < MIN_SCORE:
        return None

    return (score, latency, key)


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

    all_keys = list(dict.fromkeys(all_keys))

    semaphore = asyncio.Semaphore(CONCURRENCY)

    tasks = [validate(k, semaphore) for k in all_keys]
    results = await asyncio.gather(*tasks)

    valid = [r for r in results if r]

    # сортировка по score, потом по latency
    valid.sort(key=lambda x: (-x[0], x[1]))

    today = datetime.now().strftime("%d-%m-%Y")

    renamed = []

    for i, (score, latency, key) in enumerate(valid, 1):

        name = f"СЕРВЕР {i:04d} | {latency:.2f}s | ОБНОВЛЕН {today}"

        if "#" in key:
            key = key.split("#")[0]

        renamed.append(key + "#" + name)

    announce = f"#announce: АКТИВНЫХ {len(renamed)} | ОБНОВЛЕНО {today}"

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

    print(f"Готово. Валидных серверов: {len(renamed)}")


if __name__ == "__main__":
    asyncio.run(main())
