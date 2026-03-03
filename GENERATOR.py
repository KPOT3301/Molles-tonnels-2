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
MIN_SPEED_MBPS = 0.01  # ТЕСТОВЫЙ ПОРОГ: Пропускаем всё, что хоть немного шевелится

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(CHECKER_PATH, 0o755)

def main():
    # Создаем файлы сразу
    for f in [OUTPUT_FILE, PLAIN_OUTPUT]:
        with open(f, "w", encoding='utf-8') as empty_f:
            empty_f.write("")

    download_checker()
    raw_links = set()
    
    # 1. Сбор ссылок
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    if line.strip().startswith(('vless://', 'vmess://')):
                        raw_links.add(line.strip())
            except: continue

    print(f"🔗 Собрано сырых ссылок: {len(raw_links)}")
    if not raw_links: return

    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links))

    # 2. Тестирование
    print(f"🔎 Начинаем тест (порог {MIN_SPEED_MBPS} Mbps)...")
    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.google.com/gen_204", "-f", "temp.txt", "--format", "json", "--speedtest"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    # 3. Фильтрация и Логгирование
    filtered_links = []
    print("📊 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
    for node in checked_data:
        speed_bps = node.get('download', 0)
        speed_mbps = (speed_bps * 8) / (1024 * 1024)
        
        # Выводим в лог GitHub каждый сервер для диагностики
        status = "✅ PASS" if speed_mbps >= MIN_SPEED_MBPS else "❌ FAIL"
        print(f"{status} | Speed: {speed_mbps:.4f} Mbps | Link: {node.get('link')[:50]}...")
        
        if speed_mbps >= MIN_SPEED_MBPS:
            filtered_links.append(node['link'])

    # 4. Сохранение
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(filtered_links))

    today = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(f"#profile-title: 🧪 TEST-MODE-0.01\n#info: Найдено {len(filtered_links)} из {len(raw_links)}\n\n")
        f.write("\n".join(filtered_links))
            
    print(f"🏁 Итог: Сохранено {len(filtered_links)} серверов.")

if __name__ == "__main__":
    main()
