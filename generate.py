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
from concurrent.futures import ThreadPoolExecutor

MAX_FINAL = 1000
FAST_STAGE_LIMIT = 2000
MAX_PING = 1000
PING_THREADS = 400
XRAY_PARALLEL = 20
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

# ===== БЫСТРЫЙ TCP PING =====
def tcp_ping(host, port):
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=1.5):
            return int((time.time() - start) * 1000)
    except:
        return None

# ===== ПРОВЕРКА GOOGLE =====
def check_google(vless_url, index):
    local_port = 30000 + index
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
        for _ in range(10):
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=1):
                    break
            except:
                time.sleep(0.2)
        else:
            return False

        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}"
        }

        r = requests.get(
            "https://www.google.com/generate_204",
            proxies=proxies,
            timeout=5
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

        texts = await asyncio.gather(
            *[session.get(url) for url in sources]
        )

        all_vless = []
        for resp in texts:
            try:
                text = await resp.text()
                try:
                    text = base64.b64decode(text).decode()
                except:
                    pass
                all_vless += re.findall(r"vless://[^\s]+", text)
            except:
                pass

        all_vless = list(set(all_vless))
        print("Всего:", len(all_vless))

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
        index = 0

        with ThreadPoolExecutor(max_workers=XRAY_PARALLEL) as pool:
            futures = []

            for line, ping in fast:
                if len(final) >= MAX_FINAL:
                    break

                futures.append(pool.submit(check_google, line, index))
                index += 1

                if len(futures) >= XRAY_PARALLEL:
                    for f, (vless_line, ping_val) in zip(futures, fast[:len(futures)]):
                        if f.result():
                            final.append((vless_line, ping_val))
                            print("OK:", len(final))
                    futures.clear()

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
