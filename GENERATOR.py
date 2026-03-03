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
# Проверка сервера
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
# Читаем исходный список
# -------------------------------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    links = [line.strip() for line in f if line.strip()]

working = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    results = executor.map(check_server, links)

for result in results:
    if result:
        working.append(result)

# Сортировка по скорости
working.sort(key=lambda x: x[1])

# -------------------------------
# Формируем новые серверы
# -------------------------------
today = datetime.now().strftime("%d-%m-%Y")
final_links = []

for index, (link, latency) in enumerate(working, start=1):
    number = str(index).zfill(3)

    flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]{2})', link)
    flag = flag_match.group(1) if flag_match else "🌍"

    new_name = f"{flag} СЕРВЕР {number} | ОБНОВЛЕН {today}"

    base = link.split("#")[0]
    final_links.append(f"{base}#{new_name}")

active_count = len(final_links)
announce_line = f"#announce: 🚀 АКТИВНЫХ: {active_count} | 📅 {today}"

# -------------------------------
# Читаем старую шапку (всё до первой ss:// строки)
# -------------------------------
header_lines = []

if os.path.exists(OUTPUT_TXT):
    with open(OUTPUT_TXT, "r", encoding="utf-8") as f:
        old_lines = f.readlines()

    for line in old_lines:
        if line.startswith("ss://"):
            break
        if not line.startswith("#announce"):
            header_lines.append(line.strip())

# -------------------------------
# Собираем финальный файл
# -------------------------------
subscription_content = []

# возвращаем старую шапку
subscription_content.extend(header_lines)

# добавляем новый announce
subscription_content.append(announce_line)

# добавляем сервера
subscription_content.extend(final_links)

subscription_text = "\n".join(subscription_content)

# -------------------------------
# Сохраняем TXT
# -------------------------------
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write(subscription_text)

# -------------------------------
# Сохраняем BASE64
# -------------------------------
encoded = base64.b64encode(subscription_text.encode("utf-8")).decode("utf-8")

with open(OUTPUT_BASE64, "w", encoding="utf-8") as f:
    f.write(encoded)

print("\nПодписка обновлена.")
print(announce_line)
