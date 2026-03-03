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
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        st = os.stat(CHECKER_PATH)
        os.chmod(CHECKER_PATH, st.st_mode | stat.S_IEXEC)

def parse_host(link):
    try:
        if link.startswith('vless://'):
            return link.split('@')[1].split(':')[0]
        if link.startswith('vmess://'):
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None

def rename_server(link, index):
    """Жесткое переименование в простом формате для максимальной совместимости."""
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Формат: SERVER-0001-UPDATED-03-03-2026
    # Используем тире вместо пробелов и спецсимволов, чтобы Happ не ругался
    clean_name = f"SERVER-{num}-UPDATED-{today}"
    
    if link.startswith('vless://'):
        # Обрезаем всё после # и ставим наше новое простое имя
        base_part = link.split('#')[0]
        return f"{base_part}#{clean_name}"
    
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except: return link
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
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        key = line.split('#')[0]
                        if key not in raw_links_dict:
                            raw_links_dict[key] = line
            except: continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # Перезаписываем чистый список ссылок (без переименования)
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    print("🚀 Проверка через чекер...")
    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    # Оставляем живые и сортируем по скорости
    alive = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    final = []
    idx = 1
    # Нам больше не нужен IP-API, так как мы не пишем провайдера в имя. 
    # Это еще и ускорит скрипт в разы!
    for n in alive:
        final.append(rename_server(n['link'], idx))
        idx += 1

    if final:
        # Сохраняем итоговую подписку (Base64)
        sub_content = "\n".join(final)
        encoded_sub = base64.b64encode(sub_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded_sub)
        print(f"✨ Успех! Сформировано {len(final)} серверов в жестком формате.")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
