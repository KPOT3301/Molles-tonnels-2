import os, requests, base64, json, socket, datetime, time
from urllib.parse import quote

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
PLAIN_OUTPUT = 'links_plain.txt'

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
    print(f"🚀 Старт: {datetime.datetime.now()}")
    
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
                    raw_line = line.strip()
                    if raw_line.startswith(('vless://', 'vmess://')):
                        # Жесткое отсечение старых имен со скобками
                        clean_link = raw_line.split('#')[0]
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
            country = info.get('countryCode', 'UN').replace('[', '').replace(']', '')
            isp = info.get('isp', 'ISP').split()[0].replace('[', '').replace(']', '').strip(',.')
            
            # Имя строго без скобок
            name_str = f"{country} {isp} | N{str(idx).zfill(4)} | {today}"
            
            if base_link.startswith('vless://'):
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
        # 1. Сначала записываем текстовый файл (links_plain.txt)
        plain_content = "\n".join(final_configs)
        with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
            f.write(plain_content)
            
        # 2. Берем данные ПРЯМО из того, что записали в links_plain.txt
        # и кодируем их для subscription.txt
        with open(PLAIN_OUTPUT, "r", encoding='utf-8') as f:
            data_to_encode = f.read()
            
        out_data = base64.b64encode(data_to_encode.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(out_data)
            
        print(f"✨ Синхронизация завершена. {OUTPUT_FILE} создан на основе {PLAIN_OUTPUT}.")

if __name__ == "__main__":
    main()
