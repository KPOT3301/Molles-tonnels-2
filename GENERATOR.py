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

TIMEOUT = 5
XRAY_PATH = "./xray"
TEST_URL = "https://www.google.com"


# ================= TCP CHECK =================
async def tcp_check(host, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


# ================= VLESS PARSER =================
def parse_vless(link):
    parsed = urlparse(link)
    uuid = parsed.username
    host = parsed.hostname
    port = parsed.port
    params = parse_qs(parsed.query)

    def get_param(key, default=None):
        return params.get(key, [default])[0]

    return {
        "uuid": uuid,
        "host": host,
        "port": port,
        "type": get_param("type", "tcp"),
        "security": get_param("security", "none"),
        "sni": get_param("sni"),
        "path": get_param("path", ""),
        "host_header": get_param("host"),
        "serviceName": get_param("serviceName"),
        "flow": get_param("flow"),
        "pbk": get_param("pbk"),
        "sid": get_param("sid"),
    }


# ================= XRAY CONFIG BUILDER =================
def build_config(data):
    stream_settings = {
        "network": data["type"],
        "security": data["security"],
    }

    # TLS
    if data["security"] == "tls":
        stream_settings["tlsSettings"] = {
            "serverName": data["sni"] or data["host"]
        }

    # Reality
    if data["security"] == "reality":
        stream_settings["realitySettings"] = {
            "serverName": data["sni"],
            "publicKey": data["pbk"],
            "shortId": data["sid"] or "",
        }

    # WS
    if data["type"] == "ws":
        stream_settings["wsSettings"] = {
            "path": data["path"],
            "headers": {"Host": data["host_header"]} if data["host_header"] else {},
        }

    # gRPC
    if data["type"] == "grpc":
        stream_settings["grpcSettings"] = {
            "serviceName": data["serviceName"]
        }

    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": data["host"],
                    "port": int(data["port"]),
                    "users": [
                        {
                            "id": data["uuid"],
                            "encryption": "none",
                            "flow": data["flow"],
                        }
                    ],
                }
            ]
        },
        "streamSettings": stream_settings,
    }

    return {
        "inbounds": [
            {
                "port": 10808,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": False},
            }
        ],
        "outbounds": [outbound],
    }


# ================= XRAY CHECK =================
def xray_check(link):
    try:
        data = parse_vless(link)
        config = build_config(data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(json.dumps(config).encode())
            tmp_path = tmp.name

        proc = subprocess.Popen(
            [XRAY_PATH, "-config", tmp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(2)

        result = subprocess.run(
            [
                "curl",
                "--socks5",
                "127.0.0.1:10808",
                "-m",
                "8",
                TEST_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        proc.kill()
        os.remove(tmp_path)

        return result.returncode == 0

    except:
        return False


# ================= FULL CHECK =================
async def check_vless(link):
    try:
        data = parse_vless(link)

        # TCP first
        tcp_ok = await tcp_check(data["host"], data["port"])
        if not tcp_ok:
            return False

        # Xray real test
        return xray_check(link)

    except:
        return False


async def process_links(links):
    alive = []
    tasks = [check_vless(link) for link in links]
    results = await asyncio.gather(*tasks)

    for link, ok in zip(links, results):
        if ok:
            alive.append(link)

    return alive


# ================= FILE WRITE =================
def write_files(alive):
    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    update_date = moscow_time.strftime("%d-%m-%Y")

    announce = f"#announce: 🚀 РАБОЧИХ {len(alive)} | 📅 {update_date}"

    with open("Molestunnels.txt", "w", encoding="utf-8") as f:
        f.write(announce + "\n")
        for link in alive:
            f.write(link + "\n")

    encoded = base64.b64encode(
        ("\n".join([announce] + alive)).encode()
    ).decode()

    with open("Molestunnels_base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)


# ================= ENTRY =================
async def main():
    with open("sslist.txt", "r", encoding="utf-8") as f:
        links = [l.strip() for l in f if l.startswith("vless://")]

    alive = await process_links(links)
    write_files(alive)


if __name__ == "__main__":
    asyncio.run(main())
