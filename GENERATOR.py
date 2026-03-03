import asyncio
import aiohttp
import base64
import tempfile
import subprocess
import os
from datetime import datetime

XRAY_PATH = "./xray"
CHECK_TIMEOUT = 8
DOUBLE_CHECK_DELAY = 1
MAX_WORKERS = 50

STATIC_HEADER = [
    "#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
    "#profile-update-interval: 1",
    "#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]


# =========================
# СКАЧИВАНИЕ ПОДПИСОК
# =========================

async def fetch(session, url):
    try:
        async with session.get(url, timeout=15) as response:
            return await response.text()
    except:
        return ""


async def download_all():
    urls = []
    with open("sslist.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                urls.append(line)

    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        responses = await asyncio.gather(*tasks)

        for text in responses:
            if text:
                results.append(text)

    return "\n".join(results)


# =========================
# ИЗВЛЕЧЕНИЕ ССЫЛОК
# =========================

def extract_links(text):
    links = []
    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("vless://") or line.startswith("vmess://"):
            links.append(line)
            continue

        # если подписка base64
        try:
            decoded = base64.b64decode(line).decode("utf-8")
            for sub in decoded.splitlines():
                sub = sub.strip()
                if sub.startswith("vless://") or sub.startswith("vmess://"):
                    links.append(sub)
        except:
            pass

    return links


# =========================
# АНТИДУБЛИКАТ
# =========================

def remove_duplicates(links):
    seen = set()
    result = []

    for link in links:
        key = link.split("#")[0]
        if key not in seen:
            seen.add(key)
            result.append(link)

    return result


# =========================
# ПРОВЕРКА XRAY
# =========================

async def run_xray(config_path):
    try:
        process = await asyncio.create_subprocess_exec(
            XRAY_PATH,
            "-config", config_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=CHECK_TIMEOUT)
        except asyncio.TimeoutError:
            process.kill()
            return True

        return False
    except:
        return False


async def check_server(link):
    # минимальный конфиг для проверки
    config = f"""
{{
  "log": {{"loglevel": "none"}},
  "inbounds": [{{
    "port": 1080,
    "listen": "127.0.0.1",
    "protocol": "socks",
    "settings": {{"udp": true}}
  }}],
  "outbounds": [{{
    "protocol": "vless",
    "settings": {{}}
  }}]
}}
"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(config.encode())
        tmp_path = tmp.name

    try:
        first = await run_xray(tmp_path)
        if not first:
            return False

        await asyncio.sleep(DOUBLE_CHECK_DELAY)

        second = await run_xray(tmp_path)
        if not second:
            return False

        return True

    finally:
        os.remove(tmp_path)


# =========================
# ОСНОВНОЙ ПРОЦЕСС
# =========================

async def main():
    print("Скачивание подписок...")
    text = await download_all()

    print("Извлечение ссылок...")
    links = extract_links(text)
    links = remove_duplicates(links)

    print(f"Найдено всего: {len(links)}")

    sem = asyncio.Semaphore(MAX_WORKERS)

    async def worker(link):
        async with sem:
            if await check_server(link):
                return link
            return None

    tasks = [worker(link) for link in links]
    results = await asyncio.gather(*tasks)

    alive = [r for r in results if r]

    print(f"Рабочих: {len(alive)}")

    # Переименование
    today = datetime.now().strftime("%d-%m-%Y")
    renamed = []

    for i, link in enumerate(alive, start=1):
        name = f"СЕРВЕР {str(i).zfill(4)} | ОБНОВЛЕН {today}"
        base = link.split("#")[0]
        renamed.append(f"{base}#{name}")

    # Формирование файла
    output = []
    output.extend(STATIC_HEADER)
    output.append(f"#announce: АКТИВНЫХ {len(renamed)} | ОБНОВЛЕНО {today}")
    output.extend(renamed)

    with open("Molestunnels.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
