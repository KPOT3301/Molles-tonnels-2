import subprocess
import json
import os
import sys

CHECKER_PATH = "nodes-checker.exe"  # путь к checker
MAX_DELAY = 70
TIMEOUT_SECONDS = 180

YOUTUBE_TEST = "https://www.youtube.com"
CLOUDFLARE_TEST = "https://www.cloudflare.com"

INPUT_FILE = "nodes.txt"
TEMP_FILE = "temp_nodes.txt"
OUTPUT_FILE = "good_nodes.txt"


def run_checker(test_url):
    result = subprocess.run(
        [
            CHECKER_PATH,
            "-u", test_url,
            "-f", TEMP_FILE,
            "--format", "json"
        ],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )

    if result.returncode != 0:
        print(f"Ошибка checker: {result.stderr}")
        return []

    try:
        return json.loads(result.stdout)
    except:
        print("Ошибка чтения JSON")
        return []


def main():
    if not os.path.exists(INPUT_FILE):
        print("nodes.txt не найден")
        sys.exit()

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        nodes = list(set(line.strip() for line in f if line.strip()))

    print(f"Всего нод: {len(nodes)}")

    # создаем один temp файл (без гонок)
    with open(TEMP_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(nodes))

    print("Проверка YouTube...")
    yt_results = run_checker(YOUTUBE_TEST)

    print("Проверка Cloudflare...")
    cf_results = run_checker(CLOUDFLARE_TEST)

    # превращаем в словарь для быстрого доступа
    yt_dict = {r["link"]: r for r in yt_results if "delay" in r}
    cf_dict = {r["link"]: r for r in cf_results if "delay" in r}

    good_nodes = []

    for link in nodes:
        yt = yt_dict.get(link)
        cf = cf_dict.get(link)

        if not yt or not cf:
            continue

        yt_delay = yt.get("delay", 0)
        cf_delay = cf.get("delay", 0)

        # жесткая фильтрация
        if (
            0 < yt_delay <= MAX_DELAY and
            0 < cf_delay <= MAX_DELAY
        ):
            avg_delay = (yt_delay + cf_delay) / 2

            good_nodes.append({
                "link": link,
                "yt_delay": yt_delay,
                "cf_delay": cf_delay,
                "avg_delay": avg_delay
            })

    # сортировка по средней задержке
    good_nodes.sort(key=lambda x: x["avg_delay"])

    print(f"Прошли фильтр: {len(good_nodes)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for node in good_nodes:
            f.write(node["link"] + "\n")

    print("Готово. Лучшие ноды сохранены в good_nodes.txt")

    os.remove(TEMP_FILE)


if __name__ == "__main__":
    main()
