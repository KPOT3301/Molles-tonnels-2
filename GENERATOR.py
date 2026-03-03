import socket
import base64
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

INPUT_FILE = "sslist.txt"
OUTPUT_TXT = "Molestunnels.txt"
OUTPUT_BASE64 = "Molestunnels_base64.txt"

TIMEOUT = 3
MAX_WORKERS = 100

# -------------------------------
# Проверка сервера на доступность
# -------------------------------
def check_server(link):
    try:
        match = re.search(r'@(.+?):(\d+)', link)
        if not match:
            return None

        host = match.group(1)
        port = int(match.group(2))

        start = datetime.now()
        sock = socket.create_connection((host, port), timeout=TIMEOUT)
        latency = (datetime.now() - start).total_seconds()
        sock.close()

        # Убираем Канаду
        if "CA" in link.upper() or "CANADA" in link.upper():
            return None

        return (link, latency)

    except:
        return None

# -------------------------------
# Чтение исходного списка
# -------------------------------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    links = [line.strip() for line in f if line.strip()]

print(f"Всего серверов: {len(links)}")

# -------------------------------
# Проверка серверов
# -------------------------------
working = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    results = executor.map(check_server, links)

for result in results:
    if result:
        working.append(result)

print(f"Рабочих серверов: {len(working)}")

# -------------------------------
# Умная сортировка (скорость + стабильность)
# -------------------------------
# Сейчас стабильность = факт прохождения проверки
# Можно расширить позже до истории проверок

working.sort(key=lambda x: x[1])  # сортировка по latency

# -------------------------------
# Формирование имен
# -------------------------------
today = datetime.now().strftime("%d-%m-%Y")
final_links = []

for index, (link, latency) in enumerate(working, start=1):
    number = str(index).zfill(3)

    # Получаем флаг из названия (если есть emoji)
    flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]{2})', link)
    flag = flag_match.group(1) if flag_match else "🌍"

    new_name = f"{flag} СЕРВЕР {number} | ОБНОВЛЕН {today}"

    if "#" in link:
        base = link.split("#")[0]
    else:
        base = link

    final_links.append(f"{base}#{new_name}")

# -------------------------------
# Формирование announce
# -------------------------------
active_count = len(final_links)
announce_line = f"#announce: 🚀 АКТИВНЫХ: {active_count} | 📅 {today}"

subscription_content = [announce_line] + final_links
subscription_text = "\n".join(subscription_content)

# -------------------------------
# Сохранение TXT
# -------------------------------
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write(subscription_text)

# -------------------------------
# Сохранение BASE64
# -------------------------------
encoded = base64.b64encode(subscription_text.encode("utf-8")).decode("utf-8")

with open(OUTPUT_BASE64, "w", encoding="utf-8") as f:
    f.write(encoded)

print("\n" + announce_line)
print("Подписка успешно обновлена.")
