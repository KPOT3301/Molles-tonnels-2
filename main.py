import os, requests, base64, json, socket, datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'

def check_node(host, port=443, timeout=2):
    """Быстрая проверка доступности порта"""
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, int(port)))
        s.close()
        return True
    except:
        return False

def parse_node_info(link):
    """Извлечение хоста и порта"""
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

def main():
    print(f"🚀 Start update: {datetime.datetime.now()}")
    
    unique_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
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
                            unique_links[clean_link] = line.strip()
            except: continue

    if not unique_links:
        print("❌ No links found"); return

    print(f"🔍 Checking {len(unique_links)} nodes...")
    final_configs = []
    idx = 1
    today = datetime.datetime.now().strftime("%d-%m-%Y")

    for base_link, full_link in unique_links.items():
        host, port = parse_node_info(full_link)
        
        if host and check_node(host, port):
            # МАКСИМАЛЬНО ПРОСТОЕ ИМЯ ДЛЯ HAPP
            name = f"SERVER {str(idx).zfill(4)} | UPDATED {today}"
            
            if full_link.startswith('vless://'):
                # Склеиваем строго: техническая_часть#Имя
                final_configs.append(f"{base_link}#{name}")
            else: # vmess
                try:
                    data = json.loads(base64.b64decode(full_link[8:]).decode('utf-8'))
                    data['ps'] = name
                    final_configs.append("vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8'))
                except: continue
            
            idx += 1
            if idx > 200: break # Лимит для стабильности подписки

    if final_configs:
        out_data = base64.b64encode("\n".join(final_configs).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w") as f:
            f.write(out_data)
        print(f"✨ Success! Saved {len(final_configs)} nodes.")
    else:
        print("🛑 No working nodes found.")

if __name__ == "__main__":
    main()
