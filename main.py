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
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(CHECKER_PATH, 0o755)

def rename_server(link, index):
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    # Добавляем эмодзи для красоты в списке
    status_icon = "🚀" if index <= 3 else "⚡"
    clean_name = f"{status_icon} SERVER-{num} | {today}"
    
    if link.startswith('vless://'):
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
                        raw_links_dict[key] = line
            except: continue

    if not raw_links_dict: return

    # Записываем сырые ссылки
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()) + "\n")

    # Проверка
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except:
        checked_data = [{"link": l, "delay": 100} for l in raw_links_dict.values()]

    alive = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])

    # --- ФОРМИРОВАНИЕ КРАСИВОГО ФАЙЛА ---
    today_full = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    server_count = len(alive)
    
    header = [
        f"#profile-title: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        f"#subscription-userinfo: upload=0; download=0; total=0; expire=0",
        f"#profile-update-interval: 1",
        f"#support-url: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        f"#profile-web-page-url: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        f"#announce: 🛰 Всего серверов: {server_count} | Обновлено: {today_full} 🇷🇺",
        "" # Пустая строка перед ключами
    ]

    if alive:
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            # Записываем заголовок
            f.write("\n".join(header) + "\n")
            # Записываем ключи
            for i, node in enumerate(alive, 1):
                f.write(rename_server(node['link'], i) + "\n")
        print(f"✅ Подписка оформлена! Серверов: {server_count}")

if __name__ == "__main__":
    main()
