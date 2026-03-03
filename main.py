import os, requests, base64, json, socket, datetime, time
from urllib.parse import quote

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'

def check_node(host, port=443, timeout=2):
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, int(port)))
        s.close()
        return True
    except:
        return False

def parse_node_info(link):
    try:
        if link.startswith('vless://'):
            part = link.split('@')[1].replace('?', '#').split('#')[0]
            host = part.split(':')[0]
            port = part.split(':')[1] if ':' in part else 443
            return host, port
        if link.startswith('vmess://'):
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return data.get('add'), data.get('port', 443)
    except:
        return None, None

def get_ip_info(host):
    try:
        ip = socket.gethostbyname(host)
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,isp", timeout=5).json()
        if res.get('status') == 'success':
            return res
    except: pass
    return {'countryCode': 'UN', 'isp': 'Unknown'}

def main():
    print(f"🚀 Запуск обновления (без скобок): {datetime.datetime.now()}")
    
    unique_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                content = r.text
                try: content = base64.b64decode(content.strip()).decode('utf-8')
                except: pass
                for line in content.splitlines():
                    if line.strip().startswith(('vless://', 'vmess://')):
                        clean_link = line.strip().split('#')[0]
                        if clean_link not in unique_links:
                            unique_links[clean_link] = clean_link
            except: continue

    if not unique_links:
        print("❌ Ссылки не найдены"); return

    print(f"🔍 Проверка {len(unique_links)} узлов...")
    final_configs = []
    idx = 1
    today = datetime.datetime.now().strftime("%d-%m-%Y")

    for base_link in unique_links.keys():
        host, port = parse_node_info(base_link)
        
        if host and check_node(host, port):
            info = get_ip_info(host)
            country = info.get('countryCode', 'UN')
            isp = info.get('isp', 'ISP').split()[0].strip(',.')
            
            # ФОРМАТ БЕЗ СКОБОК: US DigitalOcean | №0001 | 03-03-2026
            name_str = f"{country} {isp} | №{str(idx).zfill(4)} | {today}"
            
            if base_link.startswith('vless://'):
                # Кодируем имя для безопасности URL
                final_configs.append(f"{base_link}#{quote(name_str)}")
            elif base_link.startswith('vmess://'):
                try:
                    data = json.loads(base64.b64decode(base_link[8:]).decode('utf-8'))
                    data['ps'] = name_str
                    final_configs.append("vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8'))
                except: continue
            
            idx += 1
            if idx % 15 == 0: time.sleep(1) 
            if idx > 400: break

    if final_configs:
        out_data = base64.b64encode("\n".join(final_configs).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(out_data)
        print(f"✨ Готово! Сохранено {len(final_configs)} серверов без скобок.")

if __name__ == "__main__":
    main()
