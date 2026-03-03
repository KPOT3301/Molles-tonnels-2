import os
import requests
import base64
import json
import subprocess
import stat
import time
import socket
import datetime
from urllib.parse import urlparse, urlunparse, quote, unquote

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL)
        with open(CHECKER_PATH, "wb") as f: f.write(r.content)
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)

def parse_host(link):
    try:
        if link.startswith('vless://'):
            # Извлекаем хост из vless://uuid@host:port...
            return link.split('@')[1].split(':')[0].split('?')[0]
        if link.startswith('vmess://'): 
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None
    return None

def get_batch_ip_info(hosts):
    ips_to_query, host_to_ip = [], {}
    for h in hosts:
        try:
            ip = socket.gethostbyname(h)
            ips_to_query.append(ip)
            host_to_ip[h] = ip
        except: continue
    if not ips_to_query: return {}
    try:
        unique_ips = list(set(ips_to_query))[:BATCH_SIZE]
        url = "http://ip-api.com/batch?fields=status,query,countryCode,isp,proxy"
        res = requests.post(url, json=unique_ips, timeout=10).json()
        ip_map = {i['query']: i for i in res if i.get('status') == 'success'}
        return {h: ip_map[ip] for h, ip in host_to_ip.items() if ip in ip_map}
    except: return {}

def rename_server(link, info, index):
    """Безопасное переименование без поломки параметров протокола."""
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'Unknown').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Новое название
    new_ps = f"[{flag}] {isp} | №{num} | {date}"

    if link.startswith('vless://'):
        # Убираем старое имя после # если оно есть
        base_part = link.split('#')[0]
        # quote нужен, чтобы спецсимволы не ломали парсинг в приложении
        return f"{base_part}#{quote(new_ps)}"
        
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = new_ps # В vmess название хранится в поле ps
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except:
            return link
    return link

def main():
    download_checker()
    
    # 1. Сбор и дедупликация
    raw_links_dict = {} 
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [line.strip() for line in f if line.strip()]
        
        for url in sources:
            try:
                print(f"📡 Чтение источника: {url}")
                r = requests.get(url, timeout=15)
                data = r.text
                # Пробуем декодировать если весь файл в base64
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in data.splitlines():
                    link = line.strip()
                    if link.startswith(('vless://', 'vmess://')):
                        # Ключ для дедупликации - ссылка без имени
                        link_body = link.split('#')[0]
                        if link_body not in raw_links_dict:
                            raw_links_dict[link_body] = link
            except Exception as e:
                print(f"⚠️ Ошибка при чтении {url}: {e}")

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # 2. Проверка YouTube (Ядро Xray)
    print(f"🚀 Проверка {len(raw_links_dict)} серверов...")
    with open("temp.txt", "w") as f:
        f.write("\n".join(raw_links_dict.values()))
    
    res = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], capture_output=True, text=True)
    
    try:
        checked_data = json.loads(res.stdout)
    except:
        print("❌ Ошибка парсинга результатов чекера.")
        return

    # Фильтруем только рабочие и сортируем по задержке
    alive_nodes = [n for n in checked_data if n.get('delay', 0) > 0]
    alive_nodes.sort(key=lambda x: x.get('delay', 9999))

    # 3. Анализ IP и переименование
    print(f"🌍 Фильтрация IP и провайдеров...")
    final_links = []
    current_index = 1 
    
    for i in range(0, len(alive_nodes), BATCH_SIZE):
        chunk = alive_nodes[i:i+BATCH_SIZE]
        hosts = [parse_host(n['link']) for n in chunk if parse_host(n['link'])]
        info_map = get_batch_ip_info(hosts)
        
        for n in chunk:
            host = parse_host(n['link'])
            info = info_map.get(host)
            
            # Исключаем Cloudflare (часто лагает в Hiddify)
            if info and "Cloudflare" not in info.get('isp', ''):
                renamed = rename_server(n['link'], info, current_index)
                final_links.append(renamed)
                current_index += 1
        
        time.sleep(1.5)

    # 4. Перезапись подписки (Base64)
    if final_links:
        encoded_data = base64.b64encode("\n".join(final_links).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded_data)
        print(f"✨ Готово! Рабочих серверов сохранено: {len(final_links)}")
    else:
        print("🛑 Ни один сервер не прошел проверку.")

if __name__ == "__main__":
    main()
