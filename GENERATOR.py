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

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(CHECKER_PATH, 0o755)

def main():
    # Создаем файлы сразу, чтобы Actions не ругался
    for f in [OUTPUT_FILE, PLAIN_OUTPUT]:
        with open(f, "w", encoding='utf-8') as empty_f:
            empty_f.write("")

    download_checker()
    raw_links = set()
    
    # 1. Сбор ссылок из links.txt
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                try: 
                    # Пробуем декодировать base64 подписки
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    clean_line = line.strip()
                    if clean_line.startswith(('vless://', 'vmess://')):
                        raw_links.add(clean_line)
            except: continue

    print(f"🔗 Найдено уникальных ссылок: {len(raw_links)}")
    if not raw_links:
        print("❌ Ссылки не собраны. Проверьте links.txt!")
        return

    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links))

    # 2. Проверка на ДОСТУПНОСТЬ (без жесткого Speedtest)
    print("🔎 Проверка доступности серверов...")
    try:
        # Убираем флаг --speedtest, оставляем обычный чек
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.google.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        # Если чекер упал, просто сохраняем все сырые ссылки
        checked_data = [{"link": l, "delay": 1} for l in raw_links]

    # 3. Отбор тех, у кого delay > 0 (сервер ответил)
    alive_nodes = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    final_links = [n['link'] for n in alive_nodes]

    # 4. Сохранение
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(final_links))

    today = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    header = [
        f"#profile-title: 🚀 КРОТ-TUNNELS-LIVE 🚀",
        f"#announce: Обновлено: {today} | Рабочих: {len(final_links)}",
        ""
    ]
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write("\n".join(header) + "\n")
        f.write("\n".join(final_links))
            
    print(f"✅ Готово! Сохранено живых серверов: {len(final_links)}")

if __name__ == "__main__":
    main()
