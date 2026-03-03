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
CACHE_MAX_AGE = 3 * 24 * 60 * 60
DECAY_FACTOR = 0.7

TIMEOUT = 12
CONCURRENCY = 50

STAGE2_LIMIT = 1_000_000
STAGE3_LIMIT = 3_000_000

MIN_LATENCY = 4
MIN_SPEED = 1


def load_servers():
    if not os.path.exists(SERVERS_FILE):
        return []
    with open(SERVERS_FILE, "r", encoding="utf-8") as f:
        return list(set(x.strip() for x in f if x.strip()))


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = time.time()
        valid = {}

        for item in data.get("servers", []):
            if now - item.get("last_checked", 0) <= CACHE_MAX_AGE:
                valid[item["url"]] = item

        return valid
    except:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"servers": list(cache.values())}, f, indent=2)


async def stage1(session, url):
    try:
        headers = {"Range": "bytes=0-10"}
        start = time.time()
        async with session.get(url, headers=headers, timeout=TIMEOUT) as r:
            if r.status not in (200, 206):
                return None
        return time.time() - start
    except:
        return None


async def speed_test(session, url, limit):
    try:
        downloaded = 0
        start = time.time()

        async with session.get(url, timeout=TIMEOUT) as r:
            if r.status not in (200, 206):
                return None

            async for chunk in r.content.iter_chunked(8192):
                downloaded += len(chunk)
                if downloaded >= limit:
                    break

        duration = time.time() - start
        if duration <= 0:
            return None

        speed = (downloaded * 8) / duration / 1_000_000
        return speed
    except:
        return None


async def test_pipeline(session, url):
    latency = await stage1(session, url)
    if latency is None or latency > MIN_LATENCY:
        return None

    speed_small = await speed_test(session, url, STAGE2_LIMIT)
    if speed_small is None or speed_small < MIN_SPEED:
        return None

    speed_large = await speed_test(session, url, STAGE3_LIMIT)
    if speed_large is None:
        return None

    final_speed = (speed_small + speed_large) / 2
    score = final_speed * 0.8 + (1 / latency) * 0.2

    return {
        "url": url,
        "latency": round(latency, 3),
        "speed": round(final_speed, 2),
        "score": round(score, 3)
    }


async def main():
    servers = load_servers()
    cache = load_cache()
    now = time.time()

    if not servers:
        print("No servers found.")
        return

    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [test_pipeline(session, url) for url in servers]
        results = await asyncio.gather(*tasks)

    results = [r for r in results if r]
    tested_urls = {r["url"] for r in results}

    first_run = len(cache) == 0
    MIN_SUCCESS_RUNS = 1 if first_run else 2

    for r in results:
        url = r["url"]
        score = r["score"]

        if url in cache:
            old = cache[url]
            new_score = old["score"] * DECAY_FACTOR + score * (1 - DECAY_FACTOR)

            cache[url]["score"] = round(new_score, 3)
            cache[url]["success_runs"] += 1
            cache[url]["fail_runs"] = 0
            cache[url]["last_checked"] = now
            cache[url]["latency"] = r["latency"]
        else:
            cache[url] = {
                "url": url,
                "score": score,
                "success_runs": 1,
                "fail_runs": 0,
                "last_checked": now,
                "latency": r["latency"]
            }

    for url in list(cache.keys()):
        if url not in tested_urls:
            cache[url]["fail_runs"] += 1
            cache[url]["score"] *= 0.85

            if cache[url]["fail_runs"] >= 3:
                del cache[url]

    stable = [
        v for v in cache.values()
        if v["success_runs"] >= MIN_SUCCESS_RUNS
    ]

    stable.sort(key=lambda x: x["score"], reverse=True)
    top = stable[:MAX_SERVERS]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, s in enumerate(top, 1):
            name = f"SERVER {str(i).zfill(4)} | {datetime.utcnow().strftime('%d-%m-%Y')}"
            f.write(f"{name}\n{s['url']}\nScore: {s['score']} | Speed: {s['speed']} Mbps | Latency: {s['latency']}s\n\n")

    save_cache(cache)

    print(f"Total tested: {len(servers)}")
    print(f"Passed pipeline: {len(results)}")
    print(f"Stable servers: {len(top)}")


if __name__ == "__main__":
    asyncio.run(main())
