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
MIN_SPEED_MBPS = 5.0  # Порог отбора (5 Мбит/с)

def download_checker():
    """Загружает бинарный файл чекера, если его нет"""
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        try:
            r = requests.get(CHECKER_URL, stream=True, timeout=30)
            r.raise_for_status()
            with open(CHECKER_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            os.chmod(CHECKER_PATH, 0o755)
            print("✅ Чекер загружен и готов к работе.")
        except Exception as e:
            print(f"❌ Ошибка загрузки чекера: {e}")

def main():
    # ШАГ 0: Создаем пустые файлы, чтобы GitHub Actions не выдавал ошибку, если список будет пуст
    for f_path in [OUTPUT_FILE, PLAIN_OUTPUT]:
        with open(f_path, "w", encoding='utf-8') as f:
            f.write("")

    download_checker()
    
    raw_links = set()
    
    # ШАГ 1: Сбор ссылок из источников
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [line.strip() for line in f if line.strip()]
        
        print(f"🔗 Обработка источников: {len(sources)}")
        for url in sources:
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                # Если контент в Base64 (стандарт подписок), декодируем
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        raw_links.add(line)
            except Exception as e:
                print(f"⚠️ Ошибка доступа к источнику {url}: {e}")

    if not raw_links:
        print("❌ Новых ссылок не найдено.")
        return

    # Записываем все ссылки во временный файл для проверки
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links))

    # ШАГ 2: Запуск тестирования скорости
    print(f"🔎 Тестируем {len(raw_links)} серверов (порог {MIN_SPEED_MBPS} Mbps)...")
    try:
        # --speedtest включает реальную загрузку данных для замера Мбит/с
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.google.com/gen_204", "-f", "temp.txt", "--format", "json", "--speedtest"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Критическая ошибка при работе чекера: {e}")
        return

    # ШАГ 3: Фильтрация по реальной скорости
    filtered_links = []
    for node in checked_data:
        # download приходит в байтах в секунду. Формула: (Байты * 8) / 1024 / 1024 = Мбит/с
        speed_bps = node.get('download', 0)
        speed_mbps = (speed_bps * 8) / (1024 * 1024)
        
        if speed_mbps >= MIN_SPEED_MBPS:
            filtered_links.append(node['link'])

    # ШАГ 4: Сохранение результатов (ПЕРЕЗАПИСЬ)
    # 1. Plain-файл (только ссылки)
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(filtered_links) + "\n")

    # 2. Файл подписки (с заголовками)
    today = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    header = [
        f"#profile-title: 🚀 КРОТ-5МБ-ОТБОР 🚀",
        f"#announce: Обновлено: {today} | Найдено: {len(filtered_links)}",
        f"#profile-update-interval: 6",
        ""
    ]
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write("\n".join(header) + "\n")
        f.write("\n".join(filtered_links) + "\n")
            
    print(f"✅ Готово! Найдено быстрых серверов: {len(filtered_links)}")

if __name__ == "__main__":
    main()
