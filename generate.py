import asyncio
import aiohttp
import base64
import re
import socket
import time
import json
import subprocess
import requests
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_FINAL = 1000
FAST_STAGE_LIMIT = 2000
MAX_PING = 1000
PING_THREADS = 500
XRAY_PARALLEL = 30
OUTPUT_FILE = "Molestunnels.txt"

HEADER = """#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
"""

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

# ===== СУПЕР БЫСТРЫЙ TCP PING =====
def tcp_ping(host, port):
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=1.2):
            return int((time.time() - start) * 1000)
    except:
        return None

# ===== ПРОВЕРКА GOOGLE =====
def check_google(vless_url, index):
    local_port = 40000 + index
    parsed = urlparse(vless_url)

    config = {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "port": local_port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": parsed.hostname,
                    "port": parsed.port,
                    "users": [{
                        "id": parsed.username,
                        "encryption": "none"
                    }]
                }]
            },
            "streamSettings": {"network": "tcp"}
        }]
    }

    config_file = f"xray_{index}.json"
    with open(config_file, "w") as f:
        json.dump(config, f)

    proc = subprocess.Popen(
        ["./xray", "run", "-c", config_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        for _ in range(8):
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=0.8):
                    break
            except:
                time.sleep(0.15)
        else:
            return False

        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}"
        }

        r = requests.get(
            "https://www.google.com/generate_204",
            proxies=proxies,
            timeout=4
        )

        return r.status_code in (200, 204)

    except:
        return False

    finally:
        proc.kill()
        if os.path.exists(config_file):
            os.remove(config_file)

# ===== MAIN =====
async def main():
    async with aiohttp.ClientSession() as session:
        with open("sources.txt") as f:
            sources = [s.strip() for s in f if s.strip()]

        responses = await asyncio.gather(
            *[session.get(url) for url in sources]
        )

        all_vless = []
        for r in responses:
            try:
                text = await r.text()
                try:
                    text = base64.b64decode(text).decode()
                except:
                    pass
                all_vless += re.findall(r"vless://[^\s]+", text)
            except:
                pass

        all_vless = list(set(all_vless))
        print("Всего найдено:", len(all_vless))

        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=PING_THREADS)

        ping_tasks = []
        for line in all_vless:
            parsed = urlparse(line)
            if parsed.hostname and parsed.port:
                ping_tasks.append(
                    loop.run_in_executor(
                        executor,
                        tcp_ping,
                        parsed.hostname,
                        parsed.port
                    )
                )
            else:
                ping_tasks.append(asyncio.sleep(0, result=None))

        pings = await asyncio.gather(*ping_tasks)

        fast = []
        for line, ping in zip(all_vless, pings):
            if ping and ping <= MAX_PING:
                fast.append((line, ping))

        fast.sort(key=lambda x: x[1])
        fast = fast[:FAST_STAGE_LIMIT]

        print("После пинга:", len(fast))

        final = []

        with ThreadPoolExecutor(max_workers=XRAY_PARALLEL) as pool:
            futures = {
                pool.submit(check_google, line, i): (line, ping)
                for i, (line, ping) in enumerate(fast)
            }

            for future in as_completed(futures):
                if len(final) >= MAX_FINAL:
                    break

                result = future.result()
                line, ping = futures[future]

                if result:
                    final.append((line, ping))
                    print("OK:", len(final))

        final.sort(key=lambda x: x[1])
        final = final[:MAX_FINAL]

        print("Итог:", len(final))

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(HEADER + "\n")

            for i, (line, ping) in enumerate(final, 1):
                base = line.split("#")[0]
                code = line.upper().split("#")[-1][:2]
                country = FLAG_MAP.get(code, "🌍 Unknown")
                name = f"KPOT-{i:04d} | {country} | {ping}ms"
                f.write(f"{base}#{name}\n")

if __name__ == "__main__":
    asyncio.run(main())
