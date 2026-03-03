import os
import requests
import base64
import json
import subprocess
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "links.txt"
OUTPUT_FILE = "subscription.txt"
PLAIN_OUTPUT = "links_plain.txt"
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

MAX_DELAY = 120
TOP_LIMIT = 25
THREADS = 20  # безопасно для GitHub Actions


# ---------- Скачать чекер ----------
def download_checker():
    if not os.path.exists(CHECKER_PATH):
        r = requests.get(CHECKER_URL)
        with open(CHECKER_PATH, "wb") as f:
            f.write(r.content)
        os.chmod(CHECKER_PATH, 0o755)


# ---------- Переименование ----------
def rename_server(link, index):
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    icon = "🚀" if index <= 3 else "⚡"
    clean_name = f"{icon} SERVER-{num} | {today}"

    if link.startswith("vless://"):
        return link.split("#")[0] + "#" + clean_name

    if link.startswith("vmess://"):
        try:
            data = json.loads(base64.b64decode(link[8:]).decode())
            data["ps"] = clean_name
            return "vmess://" + base64.b64encode(
                json.dumps(data).encode()
            ).decode()
        except:
            return link

    return link


# ---------- Сбор нод ----------
def collect_nodes():
    raw = {}

    if not os.path.exists(INPUT_FILE):
        return raw

    with open(INPUT_FILE) as f:
        sources = [l.strip() for l in f if l.strip()]

    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            data = r.text.strip()
            try:
                data = base64.b64decode(data).decode()
            except:
                pass

            for line in data.splitlines():
                line = line.strip()
                if line.startswith(("vless://", "vmess://")):
                    raw[line.split("#")[0]] = line
        except:
            continue

    return raw


# ---------- Проверка одной ноды ----------
def check_node(link):
    try:
        with open("temp_single.txt", "w") as f:
            f.write(link)

        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com",
             "-f", "temp_single.txt", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=25
        )

        data = json.loads(res.stdout)
        if data and data[0].get("delay", 0) > 0:
            return {
                "link": link,
                "delay": data[0]["delay"]
            }
    except:
        pass

    return None


# ---------- Основной запуск ----------
def main():
    download_checker()
    nodes = collect_nodes()

    if not nodes:
        return

    # сохраняем сырой список
    with open(PLAIN_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(nodes.values()))

    results = []

    # ПАРАЛЛЕЛЬНАЯ ПРОВЕРКА
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(check_node, link): link
                   for link in nodes.values()}

        for future in as_completed(futures):
            result = future.result()
            if result and result["delay"] <= MAX_DELAY:
                results.append(result)

    if not results:
        return

    # Рейтинг
    for node in results:
        node["score"] = 1000 / node["delay"]

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    results = results[:TOP_LIMIT]

    # Заголовок
    today = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    header = [
        "#profile-title: 🚀 PREMIUM TUNNELS",
        "#profile-update-interval: 1",
        f"#announce: ⚡ Servers: {len(results)} | Updated: {today}",
        ""
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")
        for i, node in enumerate(results, 1):
            f.write(rename_server(node["link"], i) + "\n")


if __name__ == "__main__":
    main()
