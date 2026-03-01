import asyncio
import aiohttp
import base64
import re
import socket
import time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

MAX_SERVERS = 3000
MAX_PING = 1000
PING_THREADS = 300
GITHUB_THREADS = 50

OUTPUT_FILE = "Molestunnels.txt"

HEADER = """#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
"""

stop_event = asyncio.Event()
valid_servers = []
counter = 1


# ================= TCP PING =================
def tcp_ping(host, port):
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=1.5):
            return int((time.time() - start) * 1000)
    except:
        return None


# ================= COUNTRY =================
async def get_country(session, ip):
    try:
        async with session.get(
            f"http://ip-api.com/json/{ip}?fields=countryCode",
            timeout=3
        ) as r:
            data = await r.json()
            return data.get("countryCode", "UN")
    except:
        return "UN"


def flag(country):
    return "".join(chr(ord(c) + 127397) for c in country.upper())


# ================= PROCESS SERVER =================
async def process_server(session, line, executor):
    global counter

    if stop_event.is_set():
        return

    try:
        parsed = urlparse(line)
        host = parsed.hostname
        port = parsed.port

        if not host or not port:
            return

        loop = asyncio.get_running_loop()
        ping = await loop.run_in_executor(executor, tcp_ping, host, port)

        if ping is None or ping > MAX_PING:
            return

        country = await get_country(session, host)
        new_name = f"KPOT-{counter:04d}-{flag(country)}-{country}"
        counter += 1

        base = line.split("#")[0]
        final = f"{base}#{new_name}"

        valid_servers.append(final)

        if len(valid_servers) >= MAX_SERVERS:
            stop_event.set()

    except:
        pass


# ================= FETCH SOURCE =================
async def fetch_source(session, url):
    try:
        async with session.get(url, timeout=15) as r:
            text = await r.text()
            try:
                return base64.b64decode(text).decode("utf-8", errors="ignore")
            except:
                return text
    except:
        return ""


# ================= MAIN =================
async def main():
    connector = aiohttp.TCPConnector(limit=GITHUB_THREADS, ssl=False)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        with open("sources.txt", "r", encoding="utf-8") as f:
            sources = [s.strip() for s in f if s.strip()]

        texts = await asyncio.gather(
            *[fetch_source(session, url) for url in sources]
        )

        all_vless = []
        for text in texts:
            all_vless += re.findall(r"vless://[^\s]+", text)

        all_vless = list(set(all_vless))

        executor = ThreadPoolExecutor(max_workers=PING_THREADS)

        tasks = []
        for line in all_vless:
            if stop_event.is_set():
                break
            tasks.append(process_server(session, line, executor))

        await asyncio.gather(*tasks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER.strip() + "\n\n")
        for s in valid_servers:
            f.write(s + "\n")

    print(f"Готово. Найдено серверов: {len(valid_servers)}")


if __name__ == "__main__":
    asyncio.run(main())
