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
    """Извлечение хоста и порта для проверки"""
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
    print(f"🚀 Start: {datetime.datetime.now()}")
    
    unique_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                content = r.text
                try: 
                    content = base64.b64decode(content.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in content.splitlines():
                    link = line.strip()
                    if link.startswith(('vless://', 'vmess://')):
                        # Ключевое изменение: ВСЕГДА берем только часть ДО знака #
                        # Это полностью удаляет старое имя (например, [AM] Host)
                        base_link = link.split('#')[0]
                        if base_link not in unique_links:
                            unique_links[base_link] = base_link
            except: 
                continue

    if not unique_links:
        print("❌ Ссылки не найдены"); return

    print(f"🔍 Проверка {len(unique_links)} серверов...")
    final_configs = []
    idx = 1
    today = datetime.datetime.now().strftime("%d-%m-%Y")

    for base_link in unique_links.keys():
        host, port = parse_node_info(base_link)
        
        if host and check_node(host, port):
            # НОВОЕ ИМЯ: СТРОГО №0001 | 03-03-2026
            name = f"№{str(idx).zfill(4)} | {today}"
            
            if base_link.startswith('vless://'):
                # Склеиваем чистую базу и новое имя
                final_configs.append(f"{base_link}#{name}")
            elif base_link.startswith('vmess://'):
                try:
                    data = json.loads(base64.b64decode(base_link[8:]).decode('utf-8'))
                    data['ps'] = name
                    final_configs.append("vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8'))
                except: 
                    continue
            
            idx += 1
            if idx > 500: break

    if final_configs:
        # Сохраняем результат
        out_data = base64.b64encode("\n".join(final_configs).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(out_data)
        print(f"✨ Готово! Сохранено серверов: {len(final_configs)}")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
