import os
import requests
import base64
import json
import subprocess
import stat
import datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
PLAIN_OUTPUT = 'links_plain.txt'
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(CHECKER_PATH, 0o755)

def rename_server(link, index, total_count):
    # Рассчитываем порог 10% для ракет
    threshold = max(1, int(total_count * 0.1))
    icon = "🚀" if index <= threshold else "⚡"
    
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    clean_name = f"{icon} SERVER-{num} | {today}"
    
    if link.startswith('vless://'):
        return f"{link.split('#')[0]}#{clean_name}"
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    raw_links = {}
    
    # Сбор ссылок
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
                    if line.strip().startswith(('vless://', 'vmess://')):
                        raw_links[line.split('#')[0]] = line.strip()
            except: continue

    if not raw_links: return

    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links.values()) + "\n")

    # Проверка (YouTube)
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links.values()))

    try:
        res = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], 
                             capture_output=True, text=True)
        checked_data = json.loads(res.stdout)
    except: return

    alive = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    # Формирование файла с твоим заголовком
    count = len(alive)
    date_now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    
    header = [
        "#profile-title: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
        "#profile-update-interval: 1",
        "#support-url: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        "#profile-web-page-url: 🇷🇺КРОТовыеТОННЕЛИ🇷🇺",
        f"#announce: 🇷🇺 Всего серверов: {count} | Обновлено: {date_now} 🇷🇺",
        ""
    ]

    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write("\n".join(header) + "\n")
        for i, node in enumerate(alive, 1):
            f.write(rename_server(node['link'], i, count) + "\n")

if __name__ == "__main__":
    main()
