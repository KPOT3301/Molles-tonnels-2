import os
import requests
import base64
import json
import subprocess
import stat
import time
import socket
import datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 
REPO_API_URL = "https://api.github.com/repos/nndrizhu/nodes-checker/releases/latest"

def get_latest_checker_url():
    """Автоматически находит актуальную ссылку на amd64 бинарник"""
    try:
        print("🔍 Поиск актуальной версии чекера...")
        response = requests.get(REPO_API_URL, timeout=15)
        response.raise_for_status()
        assets = response.json().get('assets', [])
        for asset in assets:
            # Ищем файл, в названии которого есть 'linux' и 'amd64'
            name = asset.get('name', '').lower()
            if 'linux' in name and 'amd64' in name:
                return asset.get('browser_download_url')
        raise Exception("Не удалось найти подходящий файл в релизах репозитория.")
    except Exception as e:
        print(f"❌ Ошибка при поиске чекера: {e}")
        return None

def download_checker():
    """Скачивает чекер, используя динамическую ссылку"""
    if os.path.exists(CHECKER_PATH):
        os.remove(CHECKER_PATH)
        
    url = get_latest_checker_url()
    if not url:
        print("❌ Ссылка на чекер не найдена. Остановка.")
        exit(1)
        
    print(f"📥 Загрузка чекера из: {url}")
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        st = os.stat(CHECKER_PATH)
        os.chmod(CHECKER_PATH, st.st_mode | stat.S_IEXEC)
        print(f"✅ Чекер успешно подготовлен ({os.path.getsize(CHECKER_PATH) // 1024} KB)")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        exit(1)

def parse_host(link):
    try:
        if link.startswith('vless://'): 
            return link.split('@')[1].split(':')[0]
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
    download_checker()
    raw_links_dict = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            print(f"📡 Сбор из: {url}")
            try:
                r = requests.get(url, timeout=15)
                data = r.text
                try: data = base64.b64decode(data.strip()).decode('utf-8')
                except: pass
                for line in data.splitlines():
                    clean = line.strip()
                    if clean.startswith(('vless://', 'vmess://')):
                        raw_links_dict[clean.split('#')[0]] = clean
            except: continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    print(f"🚀 Проверка {len(raw_links_dict)} серверов...")
    with open("temp.txt", "w") as f: 
        f.write("\n".join(raw_links_dict.values()))
    
    res = subprocess.run(
        [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
        capture_output=True, text=True
    )
    
    try:
        nodes = json.loads(res.stdout)
        alive = sorted([n for n in nodes if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    print(f"🌍 Анализ IP для {len(alive)} серверов...")
    final_list = []
    idx = 1
    for i in range(0, len(alive), BATCH_SIZE):
        chunk = alive[i:i+BATCH_SIZE]
        hosts = [parse_host(n['link']) for n in chunk if parse_host(n['link'])]
        i_map = get_batch_ip_info(hosts)
        for n in chunk:
            h = parse_host(n['link'])
            info = i_map.get(h)
            if info and "Cloudflare" not in info.get('isp', ''):
                final_list.append(rename_server(n['link'], info, idx))
                idx += 1
        time.sleep(2)

    if final_list:
        content = "\n".join(final_list)
        with open(OUTPUT_FILE, "w") as f:
            f.write(base64.b64encode(content.encode('utf-8')).decode('utf-8'))
        print(f"✨ Готово! Сохранено: {len(final_list)}")
    else:
        print("🛑 Рабочих серверов не осталось.")

if __name__ == "__main__":
    main()
