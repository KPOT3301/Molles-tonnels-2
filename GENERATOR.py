import asyncio
import base64
import aiohttp
import time
from datetime import datetime

INPUT_FILE = "sslist.txt"
OUTPUT_FILE = "subscription.txt"
ANNOUNCE_FILE = "announce.txt"

TIMEOUT = 5
CHECKS = 3
MAX_STABILITY = 100  # максимальный допустимый разброс


def parse_ss(link):
    try:
        if not link.startswith("ss://"):
            return None

        main = link[5:]
        if "#" in main:
            main = main.split("#")[0]

        decoded = base64.urlsafe_b64decode(main + "=" * (-len(main) % 4)).decode()
        method_pass, server_port = decoded.split("@")
        method, password = method_pass.split(":")
        server, port = server_port.split(":")

        return {
            "method": method,
            "password": password,
            "server": server,
            "port": int(port),
            "raw": link
        }
    except:
        return None


def is_canada(text):
    text = text.lower()
    return "canada" in text or "🇨🇦" in text or " ca" in text


async def check_once(session, server, port):
    try:
        start = time.time()
        async with session.get(f"http://{server}:{port}", timeout=TIMEOUT):
            pass
        return (time.time() - start) * 1000
    except:
        return None


async def check_server(session, server_data):
    latencies = []

    for _ in range(CHECKS):
        latency = await check_once(session, server_data["server"], server_data["port"])
        if latency is not None:
            latencies.append(latency)

    if len(latencies) < 2:
        return None

    avg = sum(latencies) / len(latencies)
    stability = max(latencies) - min(latencies)

    if stability > MAX_STABILITY:
        return None

    score = avg + stability * 0.5

    server_data["score"] = score
    return server_data


async def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    parsed_servers = []

    for link in links:
        if is_canada(link):
            continue
        parsed = parse_ss(link)
        if parsed:
            parsed_servers.append(parsed)

    working = []

    async with aiohttp.ClientSession() as session:
        tasks = [check_server(session, s) for s in parsed_servers]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r:
                working.append(r)

    # сортировка по smart-score
    working.sort(key=lambda x: x["score"])

    today = datetime.now().strftime("%d-%m-%Y")

    final_links = []
    for i, server in enumerate(working, 1):
        flag = "🌍"  # если есть автоопределение — вставляется сюда
        name = f"{flag} СЕРВЕР {i:03d} | ОБНОВЛЕН {today}"

        encoded = base64.urlsafe_b64encode(
            f"{server['method']}:{server['password']}@{server['server']}:{server['port']}".encode()
        ).decode().rstrip("=")

        final_links.append(f"ss://{encoded}#{name}")

    # сохраняем подписку
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_links))

    # анонс
    announce_text = f"✅ АКТИВНЫХ СЕРВЕРОВ: {len(final_links)} | ОБНОВЛЕНО {today}"
    with open(ANNOUNCE_FILE, "w", encoding="utf-8") as f:
        f.write(announce_text)

    print(announce_text)


asyncio.run(main())
