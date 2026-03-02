import asyncio
import base64
import re
import socket
import requests
from urllib.parse import urlparse

SOURCES_FILE = "sslist.txt"
OUTPUT_FILE = "Molestunnels.txt"
BASE64_FILE = "Molestunnels_base64.txt"

FETCH_TIMEOUT = 10
CHECK_TIMEOUT = 1
MAX_CONCURRENT_CHECKS = 1000


# =========================
# FETCH
# =========================

def fetch_source(url):
    try:
        r = requests.get(url.strip(), timeout=FETCH_TIMEOUT)
        if r.status_code == 200:
            return r.text
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


def extract_configs(text):
    pattern = r"(vless://[^\s]+|vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+)"
    return re.findall(pattern, text)


# =========================
# PARSE HOST/PORT
# =========================

def parse_host_port(config):
    try:
        if config.startswith("vmess://"):
            decoded = base64.b64decode(config[8:]).decode()
            host = re.search(r'"add"\s*:\s*"([^"]+)"', decoded).group(1)
            port = int(re.search(r'"port"\s*:\s*"?(\\d+)"?', decoded).group(1))
            return host, port

        parsed = urlparse(config)
        return parsed.hostname, parsed.port
    except:
        return None, None


# =========================
# ASYNC CHECK
# =========================

async def check_alive(config, semaphore):
    host, port = parse_host_port(config)
    if not host or not port:
        return None

    try:
        # DNS filter
        socket.gethostbyname(host)
    except:
        return None

    async with semaphore:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=CHECK_TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
            return config
        except:
            return None


# =========================
# MAIN
# =========================

async def main():
    print("Reading sources...")
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = [line.strip() for line in f if line.strip()]

    print(f"Fetching {len(sources)} sources...")

    all_text = ""
    for src in sources:
        data = fetch_source(src)
        if data:
            data = decode_if_base64(data)
            all_text += data + "\n"

    print("Extracting configs...")
    configs = extract_configs(all_text)
    configs = list(set(configs))

    print(f"Total unique configs: {len(configs)}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    print("Checking alive (turbo)...")
    tasks = [check_alive(cfg, semaphore) for cfg in configs]
    results = await asyncio.gather(*tasks)

    alive = [r for r in results if r]

    print(f"Alive configs: {len(alive)}")

    alive.sort()

    print("Writing files (overwrite)...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(alive))

    base64_data = base64.b64encode("\n".join(alive).encode()).decode()

    with open(BASE64_FILE, "w", encoding="utf-8") as f:
        f.write(base64_data)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
