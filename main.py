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
INPUT_FILE = 'links.txt'         # Файл с источниками
OUTPUT_FILE = 'subscription.txt' # Итоговая подписка (ТЕКСТОВЫЙ ФАЙЛ)
PLAIN_OUTPUT = 'links_plain.txt' # Список уникальных сырых ссылок
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"

def download_checker():
    """Скачивает чекер для Linux x64."""
    if not os.path.exists(CHECKER_PATH):
        print("📥 Загрузка чекера...")
        r = requests.get(CHECKER_URL, stream=True)
        with open(CHECKER_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        st = os.stat(CHECKER_PATH)
        os.chmod(CHECKER_PATH, st.st_mode | stat.S_IEXEC)

def rename_server(link, index):
    """
    Дает серверу простое имя для Happ.
    Формат: SERVER-0001-UPDATED-03-03-2026
    """
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    clean_name = f"SERVER-{num}-UPDATED-{today}"
    
    if link.startswith('vless://'):
        # Отрезаем всё после # и ставим новое имя
        base_part = link.split('#')[0]
        return f"{base_part}#{clean_name}"
    
    elif link.startswith('vmess://'):
        try:
            # Декодируем только для того, чтобы изменить имя (ps)
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            # Кодируем обратно ВНУТРЕННИЙ JSON (это стандарт протокола vmess)
            inner_json = json.dumps(v_data).encode('utf-8')
            return "vmess://" + base64.b64encode(inner_json).decode('utf-8')
        except:
            return link
    return link

def main():
    download_checker()
    
    raw_links_dict = {}
    
    # 1. СБОР И ДЕДУПЛИКАЦИЯ
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            sources = [l.strip() for l in f if l.strip()]
        
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                data = r.text
                # Декодируем источник, если он в Base64
                try: 
                    data = base64.b64decode(data.strip()).decode('utf-8')
                except: 
                    pass
                
                for line in data.splitlines():
                    line = line.strip()
                    if line.startswith(('vless://', 'vmess://')):
                        key = line.split('#')[0]
                        if key not in raw_links_dict:
                            raw_links_dict[key] = line
            except:
                continue

    if not raw_links_dict:
        print("🛑 Ссылок не найдено.")
        return

    # Записываем чистый список уникальных сырых ссылок
    with open(PLAIN_OUTPUT, "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    # 2. ПРОВЕРКА ЧЕРЕЗ ЧЕКЕР
    with open("temp.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(raw_links_dict.values()))

    try:
        res = subprocess.run(
            [CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        checked_data = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Ошибка чекера: {e}")
        return

    # Фильтруем живые и сортируем по скорости
    alive_nodes = sorted(
        [n for n in checked_data if n.get('delay', 0) > 0], 
        key=lambda x: x['delay']
    )

    # 3. ПЕРЕИМЕНОВАНИЕ
    final_links = []
    for idx, node in enumerate(alive_nodes, start=1):
        final_links.append(rename_server(node['link'], idx))

    # 4. СОХРАНЕНИЕ В ТЕКСТ (ЖЕСТКАЯ ПЕРЕЗАПИСЬ БЕЗ BASE64)
    if final_links:
        # Объединяем ссылки просто через перенос строки
        result_text = "\n".join(final_links)
        
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            f.write(result_text)
            f.flush() # Принудительно сбрасываем буфер на диск
            os.fsync(f.fileno()) # Гарантируем запись
            
        print(f"✅ Файл {OUTPUT_FILE} перезаписан как ОБЫЧНЫЙ ТЕКСТ.")
        print(f"📊 Всего рабочих серверов: {len(final_links)}")
    else:
        print("🛑 Рабочих серверов не найдено.")

if __name__ == "__main__":
    main()
