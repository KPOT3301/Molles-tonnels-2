import os
import requests
import base64
import json
import subprocess
import stat
import time
import datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
PLAIN_OUTPUT = 'links_plain.txt'
# Прямая ссылка на бинарник для Linux x64
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    """Надежное скачивание чекера через системный wget или requests."""
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        try:
            # Пытаемся скачать через requests
            r = requests.get(CHECKER_URL, stream=True, timeout=30)
            with open(CHECKER_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            # Принудительно ставим права на исполнение
            os.chmod(CHECKER_PATH, 0o755)
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")

def rename_server(link, index):
    """Формат: SERVER-0001-UPDATED-03-03-2026 (без пробелов и спецсимволов)"""
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    clean_name = f"SERVER-{num}-UPDATED-{today}"
    
    if link.startswith('vless://'):
        base_part = link.split('#')[0]
        return f"{base_part}#{clean_name}"
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except:
            return link
    return link

def main():
    download_checker()
    
    raw_links_dict = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        key = line.split('#')[0]
                        raw_links_dict[key] = line
            except:
                continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # 1. Перезаписываем plain файл (всегда текстовый)
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()) + "\n")

    # 2. Подготовка к проверке
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    print("🚀 Запуск проверки...")
    try:
        # Проверяем наличие файла перед запуском
        if not os.path.exists(CHECKER_PATH):
            raise FileNotFoundError("Чекер не найден")
            
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка при запуске чекера: {e}")
        # Если чекер упал, запишем хотя бы непроверенные, чтобы файл не был пустой
        checked_data = [{"link": l, "delay": 100} for l in raw_links_dict.values()]

    # Фильтруем рабочие
    alive = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])

    # 3. Переименование и запись в чистый ТЕКСТ
    if alive:
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            for i, node in enumerate(alive, 1):
                new_link = rename_server(node['link'], i)
                # Пишем каждую ссылку в новую строку, без всяких кодировок!
                f.write(f"{new_link}\n")
        print(f"✅ Файл {OUTPUT_FILE} сохранен (текстовый формат).")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
