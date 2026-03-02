import asyncio
import base64
import re
import socket
import requests
from urllib.parse import urlparse

# =========================
# CONFIG
# =========================

SOURCES_FILE = "sslist.txt"
OUTPUT_FILE = "Molestunnels.txt"
BASE64_FILE = "Molestunnels_base64.txt"

FETCH_TIMEOUT = 10
CHECK_TIMEOUT = 2.5
MAX_CONCURRENT_CHECKS = 800
MAX_ALIVE = 500  # Лимит живых VLESS

# =========================
# FIXED SUBSCRIPTION HEADER
# =========================

FIXED_HEADER = [
"#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#subscription-userinfo: upload=0; download=0; total=0; expire=0",
"#profile-update-interval: 1",
"#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
"#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]

# =========================
# FETCH SOURCES
# =========================

def fetch_source(url):
    try:
        r = requests.get(url.strip(), timeout=FETCH_TIMEOUT)
        if r.status_code == 200:
            return r.text.strip()
    except:
        return ""
    return ""


def decode_if_base64(text):
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        if "://" in decoded:
            return decoded
    except:
        pass
    return text


def extract_vless(text):
    pattern = r"(vless://[^\s]+)"
    return re.findall(pattern, text)

# =========================
# PARSE HOST PORT
# =========================

def parse_host_port(config):
    try:
        parsed = urlparse(config)
        return parsed.hostname, parsed.port
    except:
        return None, None

# =========================
# CHECKING
# =========================

async def async_check(host, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=CHECK_TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


def fallback_check(host, port):
    try:
        with socket.create_connection((host, port), timeout=CHECK_TIMEOUT):
            return True
    except:
        return False


async def check_alive(config, semaphore):
    host, port = parse_host_port(config)
    if not host or not port:
        return None

    async with semaphore:
        ok = await async_check(host, port)

        if not ok:
            await asyncio.sleep(0.5)
            ok = await async_check(host, port)

        if not ok:
            ok = fallback_check(host, port)

        if ok:
            return config

    return None

# =========================
# MAIN
# =========================

async def main():

    print("Reading sources...")

    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            sources = [line.strip() for line in f if line.strip()]
    except:
        print("sslist.txt not found.")
        return

    if not sources:
        print("No sources found.")
        return

    print(f"Sources count: {len(sources)}")
    print("Fetching sources...")

    all_text = ""
    for src in sources:
        data = fetch_source(src)
        if data:
            data = decode_if_base64(data)
            all_text += data + "\n"

    print("Extracting VLESS configs only...")
    configs = list(set(extract_vless(all_text)))
    print(f"Unique VLESS configs: {len(configs)}")

    if not configs:
        print("No VLESS configs extracted.")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    print("Checking alive VLESS (early stop mode)...")

    alive = []
    tasks = set()

    for cfg in configs:
        task = asyncio.create_task(check_alive(cfg, semaphore))
        tasks.add(task)

        done, tasks = await asyncio.wait(
            tasks,
            timeout=0,
            return_when=asyncio.FIRST_COMPLETED
        )

        for d in done:
            result = d.result()
            if result:
                alive.append(result)

                if len(alive) >= MAX_ALIVE:
                    print(f"Reached {MAX_ALIVE} alive VLESS. Stopping early.")
                    for t in tasks:
                        t.cancel()
                    tasks.clear()
                    break

        if len(alive) >= MAX_ALIVE:
            break

    for t in tasks:
        try:
            result = await t
            if result and len(alive) < MAX_ALIVE:
                alive.append(result)
        except:
            pass

    alive = sorted(set(alive))

    print(f"Final alive VLESS configs: {len(alive)}")

    if len(alive) == 0:
        print("WARNING: No alive VLESS found!")
        print("Aborting overwrite to protect existing subscription.")
        exit(1)

    print("Writing files...")

    # Добавляем фиксированный header
    final_content = FIXED_HEADER + alive
    final_text = "\n".join(final_content)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_text)

    base64_data = base64.b64encode(final_text.encode()).decode()

    with open(BASE64_FILE, "w", encoding="utf-8") as f:
        f.write(base64_data)

    print("Done successfully.")


if __name__ == "__main__":
    asyncio.run(main())
