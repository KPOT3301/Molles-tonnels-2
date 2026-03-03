import os, requests, base64, json, subprocess, stat, time, socket, datetime

# --- НАСТРОЙКИ ---
INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
# Прямая ссылка на стабильный бинарник для GitHub Actions (Linux x64)
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/download/v0.6.0/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    print("📥 Загрузка чекера (v0.6.0 Linux amd64)...")
    try:
        r = requests.get(CHECKER_URL, timeout=30)
        r.raise_for_status()
        with open(CHECKER_PATH, "wb") as f:
            f.write(r.content)
        # Даем права на выполнение
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)
        print("✅ Чекер успешно загружен и готов к работе.")
    except Exception as e:
        print(f"❌ Критическая ошибка загрузки: {e}")
        exit(1)

def parse_host(link):
    try:
        if link.startswith('vless://'):
            return link.split('@')[1].split(':')[0].split('?')[0]
        if link.startswith('vmess://'):
            v_json = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            return v_json.get('add')
    except: return None

def get_ip_info(host):
    try:
        ip = socket.gethostbyname(host)
        # Используем упрощенный запрос без Batch для стабильности
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,isp", timeout=5).json()
        if res.get('status') == 'success':
            return res
    except: pass
    return None

def rename_safely(link, info, index):
    """Метод 'Хирургическое переименование': не трогаем ничего до знака #"""
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'ISP').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m")
    
    # Формируем имя без лишних спецсимволов
    new_ps = f"[{flag}] {isp} | {num} | {date}"

    if link.startswith('vless://'):
        # Просто отрезаем всё после # и ставим свое
        base_part = link.split('#')[0]
        return f"{base_part}#{new_ps}"
    
    elif link.startswith('vmess://'):
        try:
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            data['ps'] = new_ps # VMESS хранит имя внутри конфига
            return "vmess://" + base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    
    raw_links = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        
        for url in sources:
            try:
                print(f"📡 Сбор ссылок из: {url}")
                r = requests.get(url, timeout=15)
                content = r.text
                try: content = base64.b64decode(content.strip()).decode('utf-8')
                except: pass
                
                for line in content.splitlines():
                    l = line.strip()
                    if l.startswith(('vless://', 'vmess://')):
                        # Дедупликация: ключ — это ссылка без имени
                        raw_links[l.split('#')[0]] = l
            except: continue

    if not raw_links:
        print("❌ Ссылок не найдено. Проверь links.txt"); return

    print(f"🚀 Запуск проверки YouTube для {len(raw_links)} серверов...")
    with open("temp.txt", "w") as f: f.write("\n".join(raw_links.values()))
    
    # Вызываем чекер
    result = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], 
                            capture_output=True, text=True)
    
    try:
        nodes = json.loads(result.stdout)
    except:
        print("❌ Ошибка парсинга результатов чекера. Проверь вывод логов.")
        return

    # Оставляем только те, где delay > 0 и сортируем по скорости
    working = sorted([n for n in nodes if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    
    print(f"🌍 Анализ локаций для {len(working)} серверов...")
    final = []
    idx = 1
    for node in working:
        host = parse_host(node['link'])
        info = get_ip_info(host) if host else None
        
        # Если API не ответило, ставим заглушку
        info = info or {'countryCode': '??', 'isp': 'Unknown'}
        
        final.append(rename_safely(node['link'], info, idx))
        idx += 1
        time.sleep(0.4) # Защита от бана по IP в ip-api

    if final:
        # Сохраняем в Base64 для подписки
        encoded = base64.b64encode("\n".join(final).encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(encoded)
        print(f"✨ Победа! Сохранено {len(final)} серверов в {OUTPUT_FILE}")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
