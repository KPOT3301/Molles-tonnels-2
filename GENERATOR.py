import asyncio
import aiohttp
import base64
import json
from datetime import datetime

# ===================== НАСТРОЙКИ =====================

INPUT_FILE = "input.txt"          # сюда кладешь сырые ключи
OUTPUT_FILE = "subscription.txt"  # итоговая подписка
TIMEOUT = 8
CONCURRENCY = 50

# =====================================================

STATIC_LINES = [
"#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#subscription-userinfo: upload=0; download=0; total=0; expire=0",
"#profile-update-interval: 1",
"#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]


# ========= ПАРСИНГ =========

def normalize_key(key):
    return key.strip()


def is_supported(key):
    return key.startswith("vless://") or key.startswith("vmess://")


def deduplicate(keys):
    return list(dict.fromkeys(keys))


# ========= ПРОВЕРКА =========

async def check_host(session, host):
    try:
        async with session.get(f"http://{host}", timeout=TIMEOUT):
            return True
    except:
        return False


def extract_host_port(key):
    try:
        if key.startswith("vless://"):
            part = key.split("@")[1]
            host_port = part.split("?")[0]
            host = host_port.split(":")[0]
            return host

        if key.startswith("vmess://"):
            raw = key.replace("vmess://", "")
            padded = raw + "=" * (-len(raw) % 4)
            decoded = base64.b64decode(padded).decode()
            data = json.loads(decoded)
            return data.get("add")

    except:
        return None


async def validate_key(session, key):
    host = extract_host_port(key)
    if not host:
        return None

    # первая проверка
    first = await check_host(session, host)
    if not first:
        return None

    # двойная проверка
    second = await check_host(session, host)
    if not second:
        return None

    return key


# ========= ОСНОВНАЯ ЛОГИКА =========

async def main():

    print("Читаю input.txt...")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_keys = f.readlines()

    keys = [normalize_key(k) for k in raw_keys if is_supported(k)]
    keys = deduplicate(keys)

    print(f"Найдено {len(keys)} уникальных ключей")

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def sem_task(key):
            async with semaphore:
                return await validate_key(session, key)

        tasks = [sem_task(k) for k in keys]
        results = await asyncio.gather(*tasks)

    valid_keys = [r for r in results if r]

    print(f"Активных серверов: {len(valid_keys)}")

    # ======= ПЕРЕИМЕНОВАНИЕ =======

    today = datetime.now().strftime("%d-%m-%Y")

    renamed = []
    for i, key in enumerate(valid_keys, 1):
        name = f"СЕРВЕР {i:04d} | ОБНОВЛЕН {today}"

        if "#" in key:
            key = key.split("#")[0]

        key = key + "#" + name
        renamed.append(key)

    # ======= СОЗДАНИЕ ФАЙЛА =======

    announce = f"#announce: АКТИВНЫХ СЕРВЕРОВ {len(renamed)} | ОБНОВЛЕНО {today}"

    final_lines = []
    final_lines.extend(STATIC_LINES)
    final_lines.append(announce)
    final_lines.extend(renamed)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines))

    print("Готово. subscription.txt обновлен.")


if __name__ == "__main__":
    asyncio.run(main())
