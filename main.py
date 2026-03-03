import os, requests, base64, json, time, socket, datetime, concurrent.futures

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'      # Кодированный (Base64)
OUTPUT_PLAIN = 'links_plain.txt'       # Обычный текст
BATCH_SIZE = 100
CHECK_TIMEOUT = 5 
MAX_WORKERS = 50 

def parse_node(link):
    try:
        if link.startswith('vless://'):
            part = link.split('@')[1].split('?')[0].split('#')[0]
            host_port = part.split(':')
            return host_port[0], int(host_port[1])
        if link.startswith('vmess://'):
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return data.get('add'), int(data.get('port'))
    except: return None, None

def check_server(link):
    host, port = parse_node(link)
    if not host or not port: return None
    start_time = time.time()
    try:
        with socket.create_connection((host, port), timeout=CHECK_TIMEOUT):
            delay = int((time.time() - start_time) * 1000)
            return {"link": link, "delay": delay, "host": host}
    except: return None

def get_batch_ip_info(hosts):
    if not hosts: return {}
    try:
        unique_ips = list(set(hosts))[:100]
        url = "http://ip-api.com/batch?fields=status,query,countryCode,isp,proxy"
        res = requests.post(url, json=unique_ips, timeout=10).json()
        return {i['query']: i for i in res if i.get('status') == 'success'}
    except: return {}

def rename_server(link, info, index):
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'Unknown').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m-%Y")
    new_ps = f"[{flag}] {isp} | №{num} | {date}"
    
    if link.startswith('vless://'):
        return f"{link.split('#')[0]}#{new_ps}"
    if link.startswith('vmess://'):
        try:
            d = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            d['ps'] = new_ps
            return "vmess://" + base64.b64encode(json.dumps(d).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    print(f"🚀 Старт: {datetime.datetime.now()}")
    raw_links = {}
    
    # 1. Сбор и дедупликация
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        for url in sources:
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    if line.strip().startswith(('vless://', 'vmess://')):
                        raw_links[line.strip().split('#')[0]] = line.strip()
            except: continue

    # 2. Проверка
    alive_nodes = []
    if raw_links:
        print(f"📡 Проверка {len(raw_links)} серверов...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(check_server, raw_links.values()))
            alive_nodes = sorted([r for r in results if r], key=lambda x: x['delay'])

    # 3. Фильтрация и переименование
    final_list = []
    if alive_nodes:
        for i in range(0, len(alive_nodes), BATCH_SIZE):
            chunk = alive_nodes[i:i+BATCH_SIZE]
            i_map = get_batch_ip_info([n['host'] for n in chunk])
            for n in chunk:
                info = i_map.get(n['host'])
                if info and "Cloudflare" not in info.get('isp', ''):
                    final_list.append(rename_server(n['link'], info, len(final_list) + 1))
            time.sleep(1)

    # 4. Сохранение ОБОИХ файлов
    plain_content = "\n".join(final_list)
    
    # Файл 1: Обычный текст
    with open(OUTPUT_PLAIN, "w", encoding='utf-8') as f:
        f.write(plain_content)
        
    # Файл 2: Base64
    base64_content = base64.b64encode(plain_content.encode('utf-8')).decode('utf-8') if final_list else ""
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(base64_content)
        
    print(f"✨ Готово! Сохранено серверов: {len(final_list)}")

if __name__ == "__main__":
    main()
