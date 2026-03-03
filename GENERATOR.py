import asyncio
import aiohttp
import json
import os
import time
from datetime import datetime

SERVERS_FILE = "servers.txt"
CACHE_FILE = "best_cache.json"
OUTPUT_FILE = "TOP100.txt"

MAX_SERVERS = 100
MIN_SUCCESS_RUNS = 2
MAX_FAIL_RUNS = 2
CACHE_MAX_AGE = 3 * 24 * 60 * 60  # 3 days
DECAY_FACTOR = 0.7
TIMEOUT = 10
DOWNLOAD_LIMIT = 5_000_000  # 5MB max per test
CONCURRENCY = 20


# ==============================
# LOAD SERVERS
# ==============================

def load_servers():
    if not os.path.exists(SERVERS_FILE):
        return []

    with open(SERVERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ==============================
# CACHE
# ==============================

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = time.time()
        cleaned = {}

        for item in data.get("servers", []):
            if now - item.get("last_checked", 0) <= CACHE_MAX_AGE:
                cleaned[item["url"]] = item

        return cleaned

    except:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"servers": list(cache.values())}, f, indent=2)


# ==============================
# TEST SERVER
# ==============================

async def test_server(session, url):
    try:
        start_time = time.time()

        async with session.get(url, timeout=TIMEOUT) as response:
            if response.status != 200:
                return None

            downloaded = 0
            start_download = time.time()

            async for chunk in response.content.iter_chunked(1024):
                downloaded += len(chunk)
                if downloaded >= DOWNLOAD_LIMIT:
                    break

            end_download = time.time()

        latency = start_download - start_time
        duration = end_download - start_download

        if duration == 0:
            return None

        speed_mbps = (downloaded * 8) / duration / 1_000_000

        return {
            "url": url,
            "latency": round(latency, 3),
            "speed": round(speed_mbps, 2)
        }

    except:
        return None


# ==============================
# MAIN
# ==============================

async def main():
    servers = load_servers()
    cache = load_cache()
    now = time.time()

    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    results = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [test_server(session, url) for url in servers]
        responses = await asyncio.gather(*tasks)

    for r in responses:
        if r:
            results.append(r)

    tested_urls = {r["url"] for r in results}

    # ==========================
    # UPDATE CACHE
    # ==========================

    for r in results:
        url = r["url"]
        speed = r["speed"]

        if url in cache:
            old = cache[url]

            new_score = old["score"] * DECAY_FACTOR + speed * (1 - DECAY_FACTOR)

            cache[url]["score"] = round(new_score, 2)
            cache[url]["success_runs"] += 1
            cache[url]["fail_runs"] = 0
            cache[url]["last_checked"] = now
            cache[url]["latency"] = r["latency"]

        else:
            cache[url] = {
                "url": url,
                "score": speed,
                "success_runs": 1,
                "fail_runs": 0,
                "last_checked": now,
                "latency": r["latency"]
            }

    # Fail handling
    for url in list(cache.keys()):
        if url not in tested_urls:
            cache[url]["fail_runs"] += 1
            cache[url]["score"] *= 0.8

            if cache[url]["fail_runs"] >= MAX_FAIL_RUNS:
                del cache[url]

    # ==========================
    # FILTER STABLE
    # ==========================

    stable = [
        v for v in cache.values()
        if v["success_runs"] >= MIN_SUCCESS_RUNS
    ]

    stable.sort(key=lambda x: x["score"], reverse=True)
    top100 = stable[:MAX_SERVERS]

    # ==========================
    # SAVE OUTPUT
    # ==========================

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, server in enumerate(top100, 1):
            name = f"SERVER {str(i).zfill(4)} | UPDATED {datetime.utcnow().strftime('%d-%m-%Y')}"
            f.write(f"{name}\n")
            f.write(f"{server['url']}\n")
            f.write(f"Score: {server['score']} Mbps | Latency: {server['latency']}s\n\n")

    save_cache(cache)

    print(f"Done. Stable servers: {len(top100)}")


if __name__ == "__main__":
    asyncio.run(main())
