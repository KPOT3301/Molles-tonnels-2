import asyncio
import aiohttp
import base64
import re
import socket
import time
import json
import subprocess
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

MAX_FINAL = 1000
FAST_STAGE_LIMIT = 2000
MAX_PING = 1000
PING_THREADS = 400
XRAY_PARALLEL = 15

OUTPUT_FILE = "Molestunnels.txt"

HEADER = """#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
"""

def tcp_ping(host, port):
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=1.5):
            return int((time.time() - start) * 1000)
    except:
        return None


def build_xray_config(vless_url, port):
    parsed = urlparse(vless_url)
    uuid = parsed.username
    host = parsed.hostname
    server_port = parsed.port

    return {
        "inbounds": [{
            "port": port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": host,
                    "port": server_port,
                    "users": [{"id": uuid}]
                }]
            },
            "streamSettings": {"security": "tls"}
        }]
    }


def test_vless_google(vless_url, index):
    local_port = 20000 + index

    config = build_xray_config(vless_url, local_port)

    config_file = f"xray_{index}.json"
    with open(config_file, "w") as f:
        json.dump(config, f)

    proc = subprocess.Popen(
        ["./xray", "run", "-c", config_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    try:
        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}"
        }

        r = requests.get(
            "https://www.google.com/generate_204",
            proxies=proxies,
            timeout=8
        )

        return r.status_code in (200, 204)

    except:
        return False

    finally:
        proc.kill()


async def fetch_source(session, url):
    try:
        async with session.get(url, timeout=20) as r:
            text = await r.text()
            try:
                return base64.b64decode(text).decode()
            except:
                return text
    except:
        return ""


async def main():
    async with aiohttp.ClientSession() as session:

        with open("sources.txt") as f:
            sources = [s.strip() for s in f if s.strip()]

        texts = await asyncio.gather(
            *[fetch_source(session, url) for url in sources]
        )

        all_vless = []
        for text in texts:
            all_vless += re.findall(r"vless://[^\s]+", text)

        all_vless = list(set(all_vless))

        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=PING_THREADS)

        tasks = []
        for line in all_vless:
            parsed = urlparse(line)
            if not parsed.hostname or not parsed.port:
                continue
            tasks.append(
                loop.run_in_executor(
                    executor,
                    tcp_ping,
                    parsed.hostname,
                    parsed.port
                )
            )

        pings = await asyncio.gather(*tasks)

        fast = []
        for line, ping in zip(all_vless, pings):
            if ping and ping <= MAX_PING:
                fast.append((line, ping))

        fast.sort(key=lambda x: x[1])
        fast = fast[:FAST_STAGE_LIMIT]

        print("После пинга:", len(fast))

        final = []
        for i, (line, _) in enumerate(fast):
            if len(final) >= MAX_FINAL:
                break
            if test_vless_google(line, i):
                final.append(line)
                print("OK:", len(final))

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(HEADER + "\n")
            for i, line in enumerate(final, 1):
                base = line.split("#")[0]
                name = f"KPOT-{i:04d}"
                f.write(f"{base}#{name}\n")

        print("Итог:", len(final))


if __name__ == "__main__":
    asyncio.run(main())
