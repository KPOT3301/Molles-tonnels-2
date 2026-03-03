import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests

XRAY_PATH = "./xray"


# ================= DOWNLOAD SUBSCRIPTIONS =================
def download_subscriptions():
    if not os.path.exists("sslist.txt"):
        return []

    with open("sslist.txt", "r", encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.startswith("http")]

    all_links = []

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            content = r.text.strip()

            # если это base64
            try:
                decoded = base64.b64decode(content).decode("utf-8")
                content = decoded
            except:
                pass

            for line in content.splitlines():
                line = line.strip()
                if line.startswith("vless://"):
                    all_links.append(line)

        except:
            continue

    return list(set(all_links))


# ================= VLESS PARSER =================
def parse_vless(link):
    parsed = urlparse(link)
    params = parse_qs(parsed.query)

    def get(key, default=None):
        return params.get(key, [default])[0]

    return {
        "uuid": parsed.username,
        "host": parsed.hostname,
        "port": parsed.port,
        "network": get("type", "tcp"),
        "security": get("security", "none"),
        "sni": get("sni"),
        "path": get("path", ""),
        "host_header": get("host"),
        "serviceName": get("serviceName"),
        "flow": get("flow"),
        "pbk": get("pbk"),
        "sid": get("sid"),
    }


def build_config(data):
    stream = {
        "network": data["network"],
        "security": data["security"],
    }

    if data["security"] == "tls":
        stream["tlsSettings"] = {
            "serverName": data["sni"] or data["host"]
        }

    if data["security"] == "reality":
        stream["realitySettings"] = {
            "serverName": data["sni"],
            "publicKey": data["pbk"],
            "shortId": data["sid"] or ""
        }

    if data["network"] == "ws":
        stream["wsSettings"] = {
            "path": data["path"],
            "headers": {"Host": data["host_header"]} if data["host_header"] else {}
        }

    if data["network"] == "grpc":
        stream["grpcSettings"] = {
            "serviceName": data["serviceName"]
        }

    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": data["host"],
                "port": int(data["port"]),
                "users": [{
                    "id": data["uuid"],
                    "encryption": "none",
                    "flow": data["flow"]
                }]
            }]
        },
        "streamSettings": stream
    }

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [outbound]
    }


def xray_check(link):
    try:
        data = parse_vless(link)
        config = build_config(data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(json.dumps(config).encode())
            config_path = tmp.name

        proc = subprocess.Popen(
            [XRAY_PATH, "-config", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        time.sleep(3)
        alive = proc.poll() is None

        proc.kill()
        os.remove(config_path)

        return alive

    except:
        return False


async def check_vless(link):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, xray_check, link)


async def main():
    links = download_subscriptions()
    print("FOUND LINKS:", len(links))

    if not links:
        write_files([])
        return

    tasks = [check_vless(link) for link in links]
    results = await asyncio.gather(*tasks)

    alive = [l for l, ok in zip(links, results) if ok]

    print("ALIVE:", len(alive))
    write_files(alive)


def write_files(alive):
    moscow = datetime.now(ZoneInfo("Europe/Moscow"))
    date_str = moscow.strftime("%d-%m-%Y")

    announce = f"#announce: 🚀 РАБОЧИХ {len(alive)} | 📅 {date_str}"

    with open("Molestunnels.txt", "w", encoding="utf-8") as f:
        f.write(announce + "\n")
        for link in alive:
            f.write(link + "\n")

    encoded = base64.b64encode(
        ("\n".join([announce] + alive)).encode()
    ).decode()

    with open("Molestunnels_base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)


if __name__ == "__main__":
    asyncio.run(main())
