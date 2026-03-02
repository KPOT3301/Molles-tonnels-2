import requests
import base64
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

SOURCES_FILE = "ссылки.txt"
OUTPUT_FILE = "Molestunnels.txt"
BASE64_FILE = "Molestunnels_base64.txt"

HEADER = """#profile-title:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#profile-web-page-url:🇷🇺КРОТовыеТОННЕЛИ🇷🇺
#announce:🇷🇺КРОТовыеТОННЕЛИ🇷🇺

"""

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------

def get_flag(country_code):
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return ''.join(chr(ord(c.upper()) + 127397) for c in country_code)

def check_host_port(host, port):
    try:
        socket.create_connection((host, port), timeout=5)
        return True
    except:
        return False

def get_country(ip):
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=countryCode",
            timeout=5
        )
        return r.json().get("countryCode", "UN")
    except:
        return "UN"

def extract_host_port(link):
    match = re.search(r'@([^:]+):(\d+)', link)
    if match:
        return match.group(1), int(match.group(2))
    return None, None

def decode_if_base64(text):
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        if "vmess://" in decoded or "vless://" in decoded:
            return decoded
        return text
    except:
        return text

# ---------- ОСНОВНАЯ ЛОГИКА ----------

def process_link(link):
    host, port = extract_host_port(link)
    if not host or not port:
        return None

    if not check_host_port(host, port):
        return None

    country = get_country(host)
    flag = get_flag(country)

    # убираем старое имя
    if "#" in link:
        link = link.split("#")[0]

    return flag, link


def main():
    # Читаем источники
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = [line.strip() for line in f if line.strip()]

    all_links = set()

    # Скачиваем подписки
    for url in sources:
        try:
            r = requests.get(url, timeout=15)
            content = decode_if_base64(r.text)

            links = re.findall(
                r'(vmess://[^\s]+|vless://[^\s]+|trojan://[^\s]+)',
                content
            )

            all_links.update(links)

        except:
            continue

    working = []

    # Проверка в потоках (быстро для GitHub)
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(process_link, link) for link in all_links]

        for future in as_completed(futures):
            result = future.result()
            if result:
                working.append(result)

    # -------- ПЕРЕСОЗДАНИЕ ФАЙЛОВ --------
    # Файлы всегда создаются заново (режим "w")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER)

        for i, (flag, link) in enumerate(sorted(working), 1):
            name = f"{str(i).zfill(4)} {flag}"
            f.write(f"{link}#{name}\n")

    # Создание base64 версии
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        encoded = base64.b64encode(f.read().encode()).decode()

    with open(BASE64_FILE, "w", encoding="utf-8") as f:
        f.write(encoded)


if __name__ == "__main__":
    main()
