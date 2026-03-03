import asyncio
import aiohttp
import base64
import json
from datetime import datetime
import os
import time
import ssl

SS_LIST_FILE = "sslist.txt"
OUTPUT_TEXT = "Molestunnels.txt"
OUTPUT_BASE64 = "Molestunnels_base64.txt"
TIMEOUT = 8
CONCURRENCY = 50
MAX_LATENCY = 600  # ← увеличил лимит, было 450

STATIC_LINES = [
    "#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
    "#profile-update-interval: 1",
    "#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
    "#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
]

# ================= ЗАГРУЗКА =================
async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=TIMEOUT) as resp:
            return await resp.text()
    except:
        return None

def decode_if_base64(text):
    try:
        padded = text.strip() + "=" * (-len(text.strip()) % 4)
        decoded = base64.b64decode(padded).decode()
        if "vless://" in decoded or "vmess://" in decoded:
            return decoded
        return text
    except:
        return text

def extract_keys(text):
    lines = text.splitlines()
    keys = []
    for line in lines:
        line = line.strip()
        if line.startswith("vless://") or line.startswith("vmess://"):
            keys.append(line)
    return keys

# ================= ИЗВЛЕЧЕНИЕ HOST/PORT =================
def extract_host_port(key):
    try:
        if key.startswith("vless://"):
            part = key.split("@")[1]
            host_port = part.split("?")[0]
            host, port = host_port.split(":")
            return host.strip(), int(port)
        if key.startswith("vmess://"):
            raw = key.replace("vmess://", "")
            padded = raw + "=" * (-len(raw) % 4)
            data = json.loads(base64.b64decode(padded).decode())
            host = data.get("add")
            port = int(data.get("port"))
            return host.strip(), port
    except:
        return None, None

# ================= УЛУЧШЕННАЯ ПРОВЕРКА =================
async def check_tcp(host: str, port: int, retries: int = 3) -> tuple[bool, float | None]:
    for attempt in range(retries):
        try:
            start = time.perf_counter()
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=TIMEOUT)
            latency = (time.perf_counter() - start) * 1000
            writer.close()
            await writer.wait_closed()
            return True, round(latency, 1)
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            if attempt == retries - 1:
                return False, None
            await asyncio.sleep(0.4 + attempt * 0.2)
    return False, None


async def check_tls(host: str, port: int) -> tuple[bool, float | None]:
    """Мягкая TLS-проверка (отключаем проверку сертификата — для прокси это нормально)"""
    try:
        start = time.perf_counter()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE          # ← главное изменение!
        
        conn = asyncio.open_connection(
            host, port,
            ssl=context,
            server_hostname=host
        )
        reader, writer = await asyncio.wait_for(conn, timeout=TIMEOUT)
        latency = (time.perf_counter() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return True, round(latency, 1)
    except:
        return False, None


async def check_connection(key: str) -> tuple[str, float] | None:
    host, port = extract_host_port(key)
    if not host or not port:
        return None

    # 1. TCP проверка
    alive, latency = await check_tcp(host, port)
    if not alive:
        return None

    # 2. Если порт 443 — пытаемся TLS, но НЕ отбрасываем сервер, если TLS упал
    if port == 443:
        tls_alive, tls_latency = await check_tls(host, port)
        if tls_alive and tls_latency is not None:
            latency = min(latency, tls_latency)  # берём лучшее значение

    # 3. Фильтр по скорости (увеличен до 600мс)
    if latency > MAX_LATENCY:
        return None

    return key, latency


# ================= MAIN =================
async def main():
    if not os.path.exists(SS_LIST_FILE):
        print("❌ sslist.txt не найден!")
        return

    with open(SS_LIST_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"🔄 Источников в sslist.txt: {len(urls)}")

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        texts = await asyncio.gather(*[fetch_text(session, url) for url in urls])

    all_keys = []
    for text in texts:
        if not text:
            continue
        text = decode_if_base64(text)
        all_keys.extend(extract_keys(text))

    all_keys = list(dict.fromkeys(all_keys))
    print(f"📋 Уникальных конфигов: {len(all_keys)}")

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def sem_task(k):
        async with semaphore:
            return await check_connection(k)

    results = await asyncio.gather(*[sem_task(k) for k in all_keys])
    valid = [r for r in results if r]

    print(f"✅ Пройдено TCP: {len([r for r in results if r])}")
    print(f"✅ Финально активных: {len(valid)}")

    valid.sort(key=lambda x: x[1])

    today = datetime.now().strftime("%d-%m-%Y")
    renamed = []
    for i, (key, latency) in enumerate(valid, 1):
        name = f"СЕРВЕР {i:04d} | {latency}ms | ОБНОВЛЕН {today}"
        if "#" in key:
            key = key.split("#")[0]
        renamed.append(key + "#" + name)

    announce = f"#announce: АКТИВНЫХ СЕРВЕРОВ {len(renamed)} | ОБНОВЛЕНО {today}"

    final_lines = STATIC_LINES + [announce] + renamed
    final_text = "\n".join(final_lines)

    with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(final_text)

    encoded = base64.b64encode(final_text.encode()).decode()
    with open(OUTPUT_BASE64, "w", encoding="utf-8") as f:
        f.write(encoded)

    print("🎉 ГОТОВО!")
    print(f"   Файлы обновлены: {len(renamed)} активных серверов")


if __name__ == "__main__":
    asyncio.run(main())
