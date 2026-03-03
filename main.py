import os
import requests
import base64
import json
import subprocess
import stat
import time
import socket
import datetime
from urllib.parse import quote

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'      # Файл с вашими источниками (ссылками)
OUTPUT_FILE = 'subscription.txt' # Итоговая подписка
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 

def download_checker():
    """Скачивает утилиту для проверки серверов, если её нет."""
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL)
        with open(CHECKER_PATH, "wb") as f: f.write(r.content)
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)

def parse_host(link):
    """Извлекает адрес хоста из ссылки для анализа IP."""
    try:
        if link.startswith('vless://'): 
            return link.split('@')[1].split(':')[0]
        if link.startswith('vmess://'): 
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None
    return None

def get_batch_ip_info(hosts):
    """Пакетная проверка IP через API (до 100 за раз)."""
    ips_to_query = []
    host_to_ip = {}
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
        response = requests.post(url, json=unique_ips, timeout=10)
        results = response.json()
        ip_map = {item['query']: item for item in results if item.get('status') == 'success'}
        return {h: ip_map[ip] for h, ip in host_to_ip.items() if ip in ip_map}
    except: return {}

def rename_server(link, info, index):
    """Форматирует название сервера. Безопасно для Hiddify/Happ."""
    flag = info.get('countryCode', 'UN')
    isp_name = info.get('isp', 'Unknown').split()[0].strip(',. ')
    num_str = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Создаем чистое название. Используем N вместо № для совместимости.
    clean_name = f"[{flag}] {isp_name} | N{num_str} | {today}"
    
    if link.startswith('vless://'):
        # Экранируем спецсимволы в названии (пробелы, скобки) для URL
        safe_name = quote(clean_name)
        base_part = link.split('#')[0] if '#' in link else link
        return f"{base_part}#{safe_name}"
        
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name # В VMESS JSON экранирование не требуется
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    
    # 1. Сбор ссылок и удаление дублей
    raw_links_dict = {} 
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [line.strip() for line in f if line.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                # Проверка на Base64 в источнике
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    clean_line = line.strip()
                    if clean_line.startswith(('vless://', 'vmess://')):
                        # Дедупликация по телу ссылки (без учета старого названия)
                        link_body = clean_line.split('#')[0]
                        if link_body not in raw_links_dict:
                            raw_links_dict[link_body] = clean_line
            except: continue

    if not raw_links_dict:
        print("🛑 Ссылок для проверки не найдено.")
        return

    # 2. Проверка через чекер (YouTube + Latency)
    with open("temp.txt", "w") as f: f.write("\n".join(raw_links_dict.values()))
    res = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], capture_output=True, text=True)
    
    try:
        checked_data = json.loads(res.stdout)
    except:
        print("❌ Ошибка парсинга результатов чекера.")
        return

    # Оставляем только рабочие и сортируем по скорости (от быстрых к медленным)
    alive_nodes = [n for n in checked_data if n.get('delay', 0) > 0]
    alive_nodes.sort(key=lambda x: x.get('delay', 9999))

    # 3. Анализ IP и финальное формирование списка
    print(f"🌍 Анализ провайдеров для {len(alive_nodes)} серверов...")
    final_links = []
    current_index = 1 
    
    for i in range(0, len(alive_nodes), BATCH_SIZE):
        chunk = alive_nodes[i:i+BATCH_SIZE]
        hosts_list = [parse_host(n['link']) for n in chunk if parse_host(n['link'])]
        info_map = get_batch_ip_info(hosts_list)
        
        for n in chunk:
            host = parse_host(n['link'])
            info = info_map.get(host)
            
            # Фильтруем Cloudflare (часто медленный) и формируем итоговую ссылку
            if info and "Cloudflare" not in info.get('isp', ''):
                renamed = rename_server(n['link'], info, current_index)
                final_links.append(renamed)
                current_index += 1
        
        time.sleep(1.5) # Пауза для соблюдения лимитов API

    # 4. Сохранение в файл (перезапись)
    if final_links:
        encoded_data = base64.b64encode("\n".join(final_links).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded_data)
        print(f"🚀 Успех! Сформирована подписка из {len(final_links)} лучших серверов.")
    else:
        print("🛑 После всех фильтров рабочих серверов не осталось.")

if __name__ == "__main__":
    main()
