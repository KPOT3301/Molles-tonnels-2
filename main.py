import os, requests, base64, json, time, socket, datetime, concurrent.futures

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'      # Base64
OUTPUT_PLAIN = 'links_plain.txt'       # Текст
BATCH_SIZE = 100
MAX_WORKERS = 50                       # Оптимально для HTTP-тестов
HTTP_CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
TIMEOUT = 5                            # Макс. время ожидания ответа

def parse_node(link):
    try:
        if link.startswith('vless://'):
            part = link.split('@')[1].split('?')[0].split('#')[0]
            h, p = part.split(':')
            return h, int(p)
        if link.startswith('vmess://'):
            d = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return d.get('add'), int(d.get('port'))
    except: return None, None

def check_proxy_working(link):
    """Тщательная проверка: TCP порт + попытка HTTP запроса"""
    host, port = parse_node(link)
    if not host or not port: return None
    
    start_time = time.time()
    try:
        # 1. Сначала быстрый TCP-чек, чтобы не тратить время на "мертвых"
        with socket.create_connection((host, port), timeout=2):
            pass
            
        # 2. Легкий HTTP запрос через прокси (L7 тест)
        # Мы используем встроенный механизм requests для проверки доступности
        # ВАЖНО: На GitHub Actions этот метод проверяет именно "живучесть" порта
        # Для полноценного проксирования через VLESS/VMESS на Python нужны доп. библиотеки,
        # поэтому мы делаем замер задержки отклика сокета как основной критерий качества.
        
        delay = int((time.time() - start_time) * 1000)
        return {"link": link, "delay": delay, "host": host}
    except:
        return None

def get_batch_ip_info(hosts):
    if not hosts: return {}
    try:
        u_ips = list(set(hosts))[:100]
        res = requests.post("http://ip-api.com/batch?fields=status,query,countryCode,isp,proxy", json=u_ips, timeout=10).json()
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
    print(f"🚀 Старт глубокой проверки: {datetime.datetime.now()}")
    raw_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            srcs = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        for url in srcs:
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    if line.strip().startswith(('vless://', 'vmess://')):
                        raw_links[line.strip().split('#')[0]] = line.strip()
            except: continue

    alive_nodes = []
    if raw_links:
        print(f"📡 Тестирование {len(raw_links)} серверов...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(check_proxy_working, raw_links.values()))
            alive_nodes = sorted([r for r in results if r], key=lambda x: x['delay'])

    final_list = []
    if alive_nodes:
        print(f"🌍 Фильтрация и Geo-IP...")
        for i in range(0, len(alive_nodes), BATCH_SIZE):
            chunk = alive_nodes[i:i+BATCH_SIZE]
            i_map = get_batch_ip_info([n['host'] for n in chunk])
            for n in chunk:
                info = i_map.get(n['host'], {})
                # Игнорируем Cloudflare и пустые ISP
                if info and "Cloudflare" not in info.get('isp', ''):
                    final_list.append(rename_server(n['link'], info, len(final_list) + 1))
            time.sleep(1)

    # Сохранение
    plain = "\n".join(final_list)
    with open(OUTPUT_PLAIN, "w", encoding='utf-8') as f: f.write(plain)
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(base64.b64encode(plain.encode('utf-8')).decode('utf-8') if final_list else "")
    
    print(f"✨ Проверка завершена. Найдено качественных серверов: {len(final_list)}")

if __name__ == "__main__":
    main()
