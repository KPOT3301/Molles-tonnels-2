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
# Прямая ссылка на бинарник для Linux (среда GitHub)
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
MIN_SPEED_MBPS = 5.0 

def download_checker():
    # Удаляем старый чекер, чтобы скачать свежий (исключаем ошибки версий)
    if os.path.exists(CHECKER_PATH):
        os.remove(CHECKER_PATH)
    
    print("📥 Загрузка чекера...")
    r = requests.get(CHECKER_URL, stream=True)
    with open(CHECKER_PATH, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    os.chmod(CHECKER_PATH, 0o755)

def main():
    # Очищаем файлы перед началом, чтобы убедиться в перезаписи
    for f in [OUTPUT_FILE, PLAIN_OUTPUT, "temp.txt"]:
        if os.path.exists(f):
            os.remove(f)

    download_checker()
    
    unique_links = set()
    
    # 1. Сбор ссылок
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        unique_links.add(line)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки {url}: {e}")

    if not unique_links:
        print("❌ Новых ссылок не найдено.")
        return

    # Записываем во временный файл
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(list(unique_links)))

    # 2. Проверка
    print(f"🔎 Тестируем {len(unique_links)} узлов...")
    try:
        # Важно: запускаем через полную проверку скорости
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.google.com/gen_204", "-f", "temp.txt", "--format", "json", "--speedtest"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Критическая ошибка чекера: {e}")
        return

    # 3. Фильтрация
    final_nodes = []
    for n in checked_data:
        speed_bps = n.get('download', 0)
        speed_mbps = (speed_bps * 8) / (1024 * 1024)
        
        if speed_mbps >= MIN_SPEED_MBPS:
            # Сохраняем оригинальную ссылку из результата чекера
            final_nodes.append(n['link'])

    # 4. ПЕРЕЗАПИСЬ ФАЙЛОВ
    # Используем режим "w" (write), который полностью заменяет содержимое
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(final_nodes))

    today = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(f"#profile-title: 🚀 КРОТ-SPEED-FILTER\n")
        f.write(f"#announce: Обновлено: {today} | Найдено: {len(final_nodes)}\n\n")
        f.write("\n".join(final_nodes))
            
    print(f"✅ Файлы успешно перезаписаны! Серверов: {len(final_nodes)}")

if __name__ == "__main__":
    main()
