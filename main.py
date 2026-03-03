import os, requests, base64, json, socket, datetime, time

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'

def check_node(host, port=443, timeout=3):
    """Простая и надежная проверка доступности сервера"""
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, int(port)))
        s.close()
        return True
    except:
        return False

def parse_node_info(link):
    """Извлекает хост и порт для проверки"""
    try:
        if link.startswith('vless://'):
            part = link.split('@')[1].split('?')[0]
            host_port = part.split('#')[0]
            host = host_port.split(':')[0]
            port = host_port.split(':')[1] if ':' in host_port else 443
            return host, port
        if link.startswith('vmess://'):
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return data.get('add'), data.get('port', 443)
    except:
        return None, None

def get_ip_info(host):
    """Получает страну и провайдера"""
    try:
        ip = socket.gethostbyname(host)
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,isp", timeout=5).json()
        if res.get('status') == 'success':
            return res
    except: pass
    return {'countryCode': '??', 'isp': 'Unknown'}

def main():
    print(f"🚀 Запуск обновления: {datetime.datetime.now()}")
    
    unique_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            try:
                print(f"📡 Сбор из: {url}")
                r = requests.get(url, timeout=15)
                content = r.text
                try: content = base64.b64decode(content.strip()).decode('utf-8')
                except: pass
                
                for line in content.splitlines():
                    if line.strip().startswith(('vless://', 'vmess://')):
                        # Дедупликация по адресу без имени
                        clean_link = line.strip().split('#')[0]
                        if clean_link not in unique_links:
                            unique_links[clean_link] = line.strip()
            except: continue

    if not unique_links:
        print("❌ Ссылок не найдено!"); return

    print(f"🔍 Проверка {len(unique_links)} узлов...")
    final_configs = []
    idx = 1
    today = datetime.datetime.now().strftime("%d-%m")

    for base_link, full_link in unique_links.items():
        host, port = parse_node_info(full_link)
        if host and check_node(host, port):
            info = get_ip_info(host)
            flag = info.get('countryCode', 'UN')
            isp = info.get('isp', 'ISP').split()[0].strip(',.')
            name = f"[{flag}] {isp} | {str(idx).zfill(3)} | {today}"
            
            if full_link.startswith('vless://'):
                final_configs.append(f"{base_link}#{name}")
            else: # vmess
                try:
                    data = json.loads(base64.b64decode(full_link[8:]).decode('utf-8'))
                    data['ps'] = name
                    final_configs.append("vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8'))
                except: continue
            
            print(f"✅ Добавлен: {name}")
            idx += 1
            if idx % 15 == 0: time.sleep(1) # Защита от лимитов API
        
        if idx > 100: break # Ограничим до 100 лучших для стабильности

    if final_configs:
        out_data = base64.b64encode("\n".join(final_configs).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w") as f:
            f.write(out_data)
        print(f"✨ Готово! Рабочих серверов: {len(final_configs)}")

if __name__ == "__main__":
    main()
