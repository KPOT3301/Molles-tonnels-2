import os, requests, base64, json, subprocess, stat, time, socket, datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
CHECKER_PATH = "./nodes-checker"

def download_checker():
    """Автоматический поиск и загрузка последней версии чекера через API GitHub"""
    print("🔍 Поиск последней версии чекера...")
    try:
        api_url = "https://api.github.com/repos/nndrizhu/nodes-checker/releases/latest"
        release_info = requests.get(api_url, timeout=10).json()
        
        # Ищем файл именно для Linux x64
        download_url = next(asset['browser_download_url'] for asset in release_info['assets'] 
                            if "linux-amd64" in asset['name'])
        
        print(f"📥 Загрузка: {download_url}")
        r = requests.get(download_url, timeout=30)
        r.raise_for_status()
        with open(CHECKER_PATH, "wb") as f:
            f.write(r.content)
        
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)
        print("✅ Чекер готов.")
    except Exception as e:
        print(f"❌ Ошибка загрузки чекера: {e}")
        exit(1)

def parse_host(link):
    try:
        if link.startswith('vless://'):
            return link.split('@')[1].split(':')[0].split('?')[0]
        if link.startswith('vmess://'):
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None

def get_ip_info(host):
    try:
        ip = socket.gethostbyname(host)
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,isp", timeout=5).json()
        if res.get('status') == 'success':
            return res
    except: pass
    return None

def rename_safely(link, info, index):
    """Меняет ТОЛЬКО имя после знака # для VLESS, не трогая настройки сети"""
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'ISP').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m")
    
    new_ps = f"[{flag}] {isp} | {num} | {date}"

    if link.startswith('vless://'):
        # Строго сохраняем всё до знака #
        base_part = link.split('#')[0]
        return f"{base_part}#{new_ps}"
    
    elif link.startswith('vmess://'):
        try:
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            data['ps'] = new_ps
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
                print(f"📡 Сбор: {url}")
                r = requests.get(url, timeout=15)
                content = r.text
                try: content = base64.b64decode(content.strip()).decode('utf-8')
                except: pass
                
                for line in content.splitlines():
                    l = line.strip()
                    if l.startswith(('vless://', 'vmess://')):
                        raw_links[l.split('#')[0]] = l
            except: continue

    if not raw_links:
        print("❌ Ссылок не найдено"); return

    print(f"🚀 Проверка {len(raw_links)} серверов...")
    with open("temp.txt", "w") as f: f.write("\n".join(raw_links.values()))
    
    result = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], 
                            capture_output=True, text=True)
    
    try:
        nodes = json.loads(result.stdout)
    except:
        print("❌ Ошибка чекера. Проверь логи GitHub Actions."); return

    working = sorted([n for n in nodes if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    print(f"🌍 Обработка {len(working)} живых узлов...")
    final = []
    idx = 1
    for node in working:
        host = parse_host(node['link'])
        info = get_ip_info(host) if host else None
        info = info or {'countryCode': '??', 'isp': 'Unknown'}
        
        final.append(rename_safely(node['link'], info, idx))
        idx += 1
        time.sleep(0.4)

    if final:
        encoded = base64.b64encode("\n".join(final).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded)
        print(f"✨ Готово! Сохранено {len(final)} серверов.")

if __name__ == "__main__":
    main()
