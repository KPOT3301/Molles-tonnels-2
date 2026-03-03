import requests
import time
import concurrent.futures
import os
import sys

INPUT_FILE = "nodes.txt"
OUTPUT_LINKS = "links_plain.txt"
OUTPUT_SUB = "subscription.txt"

TIMEOUT = 6
MAX_DELAY = 110
FALLBACK_DELAY = 180
MAX_WORKERS = 50

YOUTUBE = "https://www.youtube.com"
CLOUDFLARE = "https://www.cloudflare.com"


def measure_delay(session, proxy, url):
    try:
        start = time.time()
        session.get(url, timeout=TIMEOUT)
        end = time.time()
        return round((end - start) * 1000)
    except:
        return None


def test_node(node):
    session = requests.Session()

    proxies = {
        "http": node,
        "https": node
    }

    session.proxies.update(proxies)

    yt_delay = measure_delay(session, node, YOUTUBE)
    cf_delay = measure_delay(session, node, CLOUDFLARE)

    if not yt_delay or not cf_delay:
        return None

    avg = (yt_delay + cf_delay) / 2

    return {
        "link": node,
        "yt": yt_delay,
        "cf": cf_delay,
        "avg": avg
    }


def filter_nodes(nodes, max_delay):
    good = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_node, n): n for n in nodes}

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if not result:
                continue

            if result["yt"] <= max_delay and result["cf"] <= max_delay:
                good.append(result)

    good.sort(key=lambda x: x["avg"])
    return good


def main():
    if not os.path.exists(INPUT_FILE):
        print("nodes.txt не найден")
        sys.exit()

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        nodes = list(set(line.strip() for line in f if line.strip()))

    print("Всего нод:", len(nodes))

    good = filter_nodes(nodes, MAX_DELAY)

    if not good:
        print("0 нод, расширяем лимит...")
        good = filter_nodes(nodes, FALLBACK_DELAY)

    print("Прошли фильтр:", len(good))

    with open(OUTPUT_LINKS, "w", encoding="utf-8") as f:
        for node in good:
            f.write(node["link"] + "\n")

    with open(OUTPUT_SUB, "w", encoding="utf-8") as f:
        for node in good:
            f.write(node["link"] + "\n")

    print("Готово.")


if __name__ == "__main__":
    main()
