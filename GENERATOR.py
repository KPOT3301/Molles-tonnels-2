import asyncio
import aiohttp
import base64
import socket
import re
import time
from urllib.parse import urlparse
from datetime import datetime
from zoneinfo import ZoneInfo

INPUT_FILE = "sslist.txt"
OUTPUT_FILE = "Molestunnels.txt"
BASE64_FILE = "Molestunnels_base64.txt"

MAX_WORKING = 500
CONCURRENCY = 300
TIMEOUT = 1.5


# -------------------- FIXED HEADERS --------------------

FIXED_HEADERS = [
    "#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
    "#profile-update-interval: 1",
    "#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
]


# -------------------- EXTRACT VLESS --------------------

def extract_vless(text):
    return list(set(re.findall(r'vless://[^\s]+', text)))


# -------------------- COUNTRY FLAG --------------------

def country_to_flag(code):
    if not code or len(code) != 2:
        return "🌍"
    return chr(ord(code[0].upper()) + 127397) + chr(ord(code[1].upper()) + 127397)


async def fetch_country(session, ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=countryCode"
        async with session.get(url, timeout=2) as resp:
            data = await resp.json()
            return country_to_flag(data.get("countryCode"))
    except:
        return "🌍"


# -------------------- FETCH SOURCES --------------------

async def fetch(session, url):
    try:
        async with session.get(url, timeout=TIMEOUT) as response:
            return await response.text()
    except:
        return ""


# -------------------- TCP CHECK --------------------

async def check_once(host, port):
    try:
        start = time.perf_counter()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=TIMEOUT
        )
        latency = (time.perf_counter() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return latency
    except:
        return None


async def check_server(config, semaphore, session):
    try:
        parsed = urlparse(config)
        host = parsed.hostname
        port = parsed.port

        if not host or not port:
            return None

        async with semaphore:
            first = await check_once(host, port)
            if first is None:
                return None

            await asyncio.sleep(0.3)

            second = await check_once(host, port)
            if second is None:
                return None

            avg_latency = (first + second) / 2

            ip = host
            try:
                ip = socket.gethostbyname(host)
            except:
                pass

            flag = await fetch_country(session, ip)

            clean_config = config.split("#")[0]

            return {
                "config": clean_config,
                "latency": avg_latency,
                "flag": flag
            }

    except:
        return None


# -------------------- MAIN --------------------

async def main():
    print("Reading sources...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            sources = [line.strip() for line in f if line.strip()]
    except:
        print("No sslist.txt found.")
        return

    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    update_date = moscow_time.strftime("%d-%m-%Y")

    async with aiohttp.ClientSession() as session:

        tasks = [fetch(session, url) for url in sources]
        results = await asyncio.gather(*tasks)

        print("Extracting VLESS configs...")

        all_configs = []
        for text in results:
            all_configs.extend(extract_vless(text))

        all_configs = list(set(all_configs))

        print(f"Total unique configs: {len(all_configs)}")

        semaphore = asyncio.Semaphore(CONCURRENCY)

        print("Checking servers...")

        tasks = [
            check_server(cfg, semaphore, session)
            for cfg in all_configs
        ]

        checked = await asyncio.gather(*tasks)

    alive = [c for c in checked if c is not None]

    if not alive:
        print("No alive configs found.")
        return

    alive.sort(key=lambda x: x["latency"])
    alive = alive[:MAX_WORKING]

    print(f"Selected fastest: {len(alive)}")

    formatted = []

    for idx, item in enumerate(alive, start=1):
        formatted.append(
            f'{item["config"]}#{item["flag"]} СЕРВЕР {idx:03d} | ОБНОВЛЕН {update_date}'
        )

    announce_line = f"#announce: 🚀 ТОП {len(formatted)} САМЫХ БЫСТРЫХ | 📅 {update_date}"

    final_text = "\n".join(FIXED_HEADERS + [announce_line] + formatted)

    print("Writing files...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_text)

    base64_data = base64.b64encode(final_text.encode()).decode()

    with open(BASE64_FILE, "w", encoding="utf-8") as f:
        f.write(base64_data)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
