import os
import requests
import base64
import json
import time
import socket
import datetime
import concurrent.futures

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
BATCH_SIZE = 100
# Таймаут для проверки сервера (в секундах)
CHECK_TIMEOUT = 5 
# Количество потоков для проверки (чем больше, тем быстрее)
MAX_WORKERS = 50

def parse_node(link):
    """Извлекает хост и порт из ссылки"""
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
    """Проверяет доступность TCP порта и замеряет задержку"""
    host, port = parse_node(link)
    if not host or not port: return None
    
    start_time = time.time()
    try:
        # Простая проверка открытия TCP порта
        with socket.create_connection((host, port), timeout=CHECK_TIMEOUT):
            delay = int((time.time() - start_time) * 1000)
            return {"link": link, "delay": delay, "host": host}
    except:
        return None

def get_batch_ip_info(hosts):
    """Получает инфо о провайдерах через Batch API"""
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
    print(f"🚀 Запуск обновления подписки: {datetime.datetime.now()}")
    raw_links = {}
    
    # 1. Сбор ссылок
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            print(f"📡 Загрузка: {url}")
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    l = line.strip()
                    if l.startswith(('vless://', 'vmess://')):
                        raw_links[l.split('#')[0]] = l
            except: continue

    if not raw_links:
        print("🛑 Ссылок не найдено."); return

    # 2. Многопоточная проверка
    print(f"⚡ Проверка {len(raw_links)} серверов в {MAX_WORKERS} потоках...")
    alive_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_server, raw_links.values()))
        alive_nodes = [r for r in results if r]

    # Сортировка по задержке
    alive_nodes.sort(key=lambda x: x['delay'])
    print(f"✅ Найдено живых серверов: {len(alive_nodes)}")

    # 3. Фильтрация IP и переименование
    final_list = []
    idx = 1
    for i in range(0, len(alive_nodes), BATCH_SIZE):
        chunk = alive_nodes[i:i+BATCH_SIZE]
        hosts = [n['host'] for n in chunk]
        i_map = get_batch_ip_info(hosts)
        
        for n in chunk:
            info = i_map.get(n['host'])
            if info and "Cloudflare" not in info.get('isp', ''):
                final_list.append(rename_server(n['link'], info, idx))
                idx += 1
        time.sleep(1)

    # 4. Сохранение
    if final_list:
        content = base64.b64encode("\n".join(final_list).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w") as f:
            f.write(content)
        print(f"✨ Готово! Файл {OUTPUT_FILE} обновлен. Серверов: {len(final_list)}")
    else:
        print("🛑 После фильтрации список пуст.")

if __name__ == "__main__":
    main()
