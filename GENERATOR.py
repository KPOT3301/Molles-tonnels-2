import os
import requests
import base64
import json
import subprocess
import datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
PLAIN_OUTPUT = 'links_plain.txt'
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
MIN_SPEED_MBPS = 5.0  # Порог отбора

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(CHECKER_PATH, 0o755)

def main():
    download_checker()
    raw_links_dict = {}
    
    # 1. Сбор ссылок из источников
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                # Пробуем декодировать Base64, если подписка зашифрована
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        # Используем саму ссылку без названия как ключ для уникальности
                        key = line.split('#')[0] if '#' in line else line
                        raw_links_dict[key] = line
            except: 
                continue

    if not raw_links_dict:
        print("❌ Ссылки не найдены.")
        return

    # Записываем все найденные во временный файл для теста
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    # 2. Проверка скоростным чекером
    print(f"🔎 Тестируем {len(raw_links_dict)} узлов. Порог: {MIN_SPEED_MBPS} Мбит/с...")
    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.google.com/gen_204", "-f", "temp.txt", "--format", "json", "--speedtest"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    # 3. Фильтрация по скорости
    # Оставляем только те серверы, где скорость >= 5 Мбит/с
    alive = []
    for n in checked_data:
        speed_bps = n.get('download', 0)
        speed_mbps = (speed_bps * 8) / (1024 * 1024)
        
        if speed_mbps >= MIN_SPEED_MBPS:
            alive.append(n['link'])

    # 4. Сохранение результатов
    # Записываем только те, что прошли отбор, в links_plain.txt
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(alive) + "\n")

    # Формируем итоговый файл подписки (без изменения имен внутри ссылок)
    today_full = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    header = [
        f"#profile-title: 🚀 КРОТ-5МБ-ONLY 🚀",
        f"#announce: 🛰 Всего быстрых серверов: {len(alive)} | Обновлено: {today_full}",
        ""
    ]

    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write("\n".join(header) + "\n")
        f.write("\n".join(alive) + "\n")
            
    print(f"✅ Готово! Сохранено серверов: {len(alive)}")

if __name__ == "__main__":
    main()
