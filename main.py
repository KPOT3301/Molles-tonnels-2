import os
import requests
import base64
import json
import subprocess
import stat
import time
import socket
import datetime
from urllib.parse import quote, urlparse

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
# Прямая ссылка на правильную архитектуру для GitHub Actions (Linux x64)
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера (Linux amd64)...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Установка прав на исполнение
        st = os.stat(CHECKER_PATH)
        os.chmod(CHECKER_PATH, st.st_mode | stat.S_IEXEC)

def parse_host(link):
    try:
        if link.startswith('vless://'):
            return link.split('@')[1].split(':')[0]
        if link.startswith('vmess://'):
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None

def get_batch_ip_info(hosts):
    ips_to_query, host_to_ip = [], {}
    for h in hosts:
        if not h: continue
        try:
            ip = socket.gethostbyname(h)
            ips_to_query.append(ip)
            host_to_ip[h] = ip
        except: continue
    if not ips_to_query: return {}
    try:
        unique_ips = list(set(ips_to_query))[:BATCH_SIZE]
        url = "http://ip-api.com/batch?fields=status,query,countryCode,isp,proxy"
        res = requests.post(url, json=unique_ips, timeout=15).json()
        ip_map = {i['query']: i for i in res if i.get('status') == 'success'}
        return {h: ip_map[ip] for h, ip in host_to_ip.items() if ip in ip_map}
    except: return {}

def rename_server(link, info, index):
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'Unknown').split()[0].strip(',. ')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m-%Y")
    
    clean_name = f"[{flag}] {isp} | N{num} | {date}"
    
    if link.startswith('vless://'):
        safe_name = quote(clean_name)
        # Удаляем старое имя и заменяем на новое
        base_part = link.split('#')[0] if '#' in link else link
        return f"{base_part}#{safe_name}"
    
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    
    raw_links_dict = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                try: 
                    # Пробуем декодировать если источник в Base64
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        # Дедупликация по адресу
                        key = line.split('#')[0]
                        if key not in raw_links_dict:
                            raw_links_dict[key] = line
            except: continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # Запись временного файла для чекера
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    print(f"🚀 Запуск проверки YouTube для {len(raw_links_dict)} узлов...")
    # Запуск чекера
    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка при работе чекера: {e}")
        return

    alive = sorted([n for n in checked_data if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    print(f"🌍 Получение инфо об IP для {len(alive)} живых серверов...")
    final = []
    idx = 1
    
    for i in range(0, len(alive), BATCH_SIZE):
        chunk = alive[i:i+BATCH_SIZE]
        h_list = [parse_host(n['link']) for n in chunk]
        i_map = get_batch_ip_info(h_list)
        
        for n in chunk:
            host = parse_host(n['link'])
            info = i_map.get(host)
            if info and "Cloudflare" not in info.get('isp', ''):
                final.append(rename_server(n['link'], info, idx))
                idx += 1
        time.sleep(1.5)

    if final:
        sub_content = "\n".join(final)
        encoded_sub = base64.b64encode(sub_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded_sub)
        print(f"✨ Готово! Рабочих серверов: {len(final)}")
    else:
        print("🛑 После фильтрации ничего не осталось.")

if __name__ == "__main__":
    main()
