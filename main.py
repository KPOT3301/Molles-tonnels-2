import os, requests, base64, json, subprocess, stat, time, socket, datetime
from urllib.parse import urlparse, parse_qs, urlencode, unquote

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
# Прямая ссылка на проверенную версию чекера для Linux x64
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/download/v0.6.0/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    print("📥 Загрузка чекера (Linux amd64)...")
    r = requests.get(CHECKER_URL, stream=True)
    if r.status_code == 200:
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Установка прав на запуск
        st = os.stat(CHECKER_PATH)
        os.chmod(CHECKER_PATH, st.st_mode | stat.S_IEXEC)
    else:
        raise Exception("Не удалось скачать чекер!")

def parse_host(link):
    try:
        if link.startswith('vless://'):
            return link.split('@')[1].split(':')[0].split('?')[0]
        if link.startswith('vmess://'):
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None

def get_ip_info(host):
    """Одиночный запрос к API для надежности (т.к. серверов обычно не 3000 после чекера)"""
    try:
        ip = socket.gethostbyname(host)
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,isp", timeout=5).json()
        if res.get('status') == 'success':
            return res
    except: pass
    return None

def rename_safely(link, info, index):
    """Меняет только имя, не ломая технические параметры"""
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'ISP').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m") # Укоротил дату для красоты
    
    new_name = f"[{flag}] {isp} | №{num} | {date}"

    if link.startswith('vless://'):
        # Отрезаем всё после # и приклеиваем новое имя
        base = link.split('#')[0]
        return f"{base}#{new_name}"
    
    elif link.startswith('vmess://'):
        try:
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            data['ps'] = new_name
            return "vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    
    raw_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            try:
                print(f"📡 Чтение: {url}")
                r = requests.get(url, timeout=15)
                content = r.text
                try: content = base64.b64decode(content.strip()).decode('utf-8')
                except: pass
                
                for line in content.splitlines():
                    l = line.strip()
                    if l.startswith(('vless://', 'vmess://')):
                        # Дедупликация по телу ссылки
                        raw_links[l.split('#')[0]] = l
            except: continue

    if not raw_links:
        print("❌ Ссылок не найдено"); return

    print(f"🚀 Проверка {len(raw_links)} уникальных серверов...")
    with open("temp.txt", "w") as f: f.write("\n".join(raw_links.values()))
    
    # Запуск чекера
    process = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], 
                            capture_output=True, text=True)
    
    try:
        results = json.loads(process.stdout)
    except:
        print("❌ Ошибка чекера. Вывод:", process.stderr); return

    working = sorted([n for n in results if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    print(f"🌍 Обработка {len(working)} живых серверов...")
    final = []
    idx = 1
    for node in working:
        host = parse_host(node['link'])
        info = get_ip_info(host) if host else None
        
        # Если API не ответило, используем заглушку, но не удаляем сервер
        info = info or {'countryCode': '??', 'isp': 'Unknown'}
        
        final.append(rename_safely(node['link'], info, idx))
        idx += 1
        time.sleep(0.5) # Маленькая пауза для IP-API

    if final:
        with open(OUTPUT_FILE, "w") as f:
            f.write(base64.b64encode("\n".join(final).encode()).decode())
        print(f"✨ Готово! Сохранено: {len(final)}")

if __name__ == "__main__":
    main()
