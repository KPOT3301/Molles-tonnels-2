import os
import requests
import base64
import json
import subprocess
import stat
import time
import socket
import datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
PLAIN_OUTPUT = 'links_plain.txt'
# Прямая ссылка на Linux amd64 версию чекера
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Выставляем права на запуск
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)

def rename_server(link, index):
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    # Самый простой формат без спецсимволов для Happ
    clean_name = f"SERVER-{num}-UPDATED-{today}"
    
    if link.startswith('vless://'):
        base_part = link.split('#')[0]
        return f"{base_part}#{clean_name}"
    
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            # Внутренний JSON vmess обязан быть в base64 по стандарту протокола
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except:
            return link
    return link

def main():
    download_checker()
    raw_links_dict = {}
    
    # 1. Сбор ссылок
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
                        if key not in raw_links_dict:
                            raw_links_dict[key] = line
            except:
                continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # Очищаем и записываем plain файл
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()) + "\n")

    # 2. Проверка
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    print("🚀 Проверка серверов...")
    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    alive_nodes = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])

    # 3. Переименование и сохранение в ТЕКСТ
    final_links = []
    for idx, node in enumerate(alive_nodes, start=1):
        final_links.append(rename_server(node['link'], idx))

    if final_links:
        # ЗАПИСЬ В ВИДЕ ОБЫЧНОГО ТЕКСТА (каждая ссылка с новой строки)
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            for link in final_links:
                f.write(link + "\n") # Явно добавляем перенос строки
        
        print(f"✅ Готово! Файл {OUTPUT_FILE} теперь в текстовом формате.")
        print(f"📊 Найдено рабочих: {len(final_links)}")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
