import asyncio
import aiohttp
import base64
import json
from datetime import datetime
import os

SS_LIST_FILE = "sslist.txt"
OUTPUT_FILE = "subscription.txt"
TIMEOUT = 8
CONCURRENCY = 50

STATIC_LINES = [
"#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#subscription-userinfo: upload=0; download=0; total=0; expire=0",
"#profile-update-interval: 1",
"#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]


# ===================== ЗАГРУЗКА ПОДПИСОК =====================

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


# ===================== ПРОВЕРКА =====================

def extract_host(key):
    try:
        if key.startswith("vless://"):
            part = key.split("@")[1]
            return part.split(":")[0]

        if key.startswith("vmess://"):
            raw = key.replace("vmess://", "")
            padded = raw + "=" * (-len(raw) % 4)
            data = json.loads(base64.b64decode(padded).decode())
            return data.get("add")
    except:
        return None


async def check_host(session, host):
    try:
        async with session.get(f"http://{host}", timeout=TIMEOUT):
            return True
    except:
        return False


async def validate(session, key):
    host = extract_host(key)
    if not host:
        return None

    first = await check_host(session, host)
    if not first:
        return None

    second = await check_host(session, host)
    if not second:
        return None

    return key


# ===================== MAIN =====================

async def main():

    if not os.path.exists(SS_LIST_FILE):
        print("sslist.txt не найден.")
        return

    print("Читаю sslist.txt...")

    with open(SS_LIST_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        # скачиваем все подписки
        texts = await asyncio.gather(*[fetch_text(session, url) for url in urls])

        all_keys = []

        for text in texts:
            if not text:
                continue

            text = decode_if_base64(text)
            keys = extract_keys(text)
            all_keys.extend(keys)

        # антидубликат
        all_keys = list(dict.fromkeys(all_keys))

        print(f"Всего собрано ключей: {len(all_keys)}")

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def sem_task(k):
            async with semaphore:
                return await validate(session, k)

        results = await asyncio.gather(*[sem_task(k) for k in all_keys])

    valid = [r for r in results if r]

    print(f"Активных серверов: {len(valid)}")

    today = datetime.now().strftime("%d-%m-%Y")

    renamed = []
    for i, key in enumerate(valid, 1):
        name = f"СЕРВЕР {i:04d} | ОБНОВЛЕН {today}"

        if "#" in key:
            key = key.split("#")[0]

        renamed.append(key + "#" + name)

    announce = f"#announce: АКТИВНЫХ СЕРВЕРОВ {len(renamed)} | ОБНОВЛЕНО {today}"

    final = []
    final.extend(STATIC_LINES)
    final.append(announce)
    final.extend(renamed)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final))

    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
