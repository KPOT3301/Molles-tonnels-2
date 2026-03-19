#!/usr/bin/env python3
# GENERATOR.py – Финальная версия с фильтрацией только российских серверов и speed-тестом
# Проверка реальных сайтов: только Google.
# Чередование регионов заменено на приоритет России.
# Добавлен этап SPEED-теста для топ-50 серверов.

import os
import re
import socket
import ssl
import base64
import logging
import subprocess
import time
import json
import tempfile
import sys
import random
import threading
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from datetime import datetime

# =============================================================================
# НАСТРОЙКИ (можно изменять)
# =============================================================================

# ---------- Общие настройки ----------
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "subscription.txt"
OUTPUT_BASE64_FILE = "subscription_base64.txt"
REQUEST_TIMEOUT = 10
SING_BOX_PATH = "./sing-box"

# ---------- Настройки подписки ----------
PROFILE_TITLE = "🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
SUPPORT_URL = "🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
PROFILE_WEB_PAGE_URL = "🇷🇺КРОТовыеТОННЕЛИ🇷🇺"
PROFILE_UPDATE_INTERVAL = "1"
SUBSCRIPTION_USERINFO = "upload=0; download=0; total=0; expire=0"

# ---------- Геоданные ----------
GEOIP_DB_PATH = "GeoLite2-City.mmdb"
GEOIP_DB_URL = "https://raw.githubusercontent.com/P3TERX/GeoLite.mmdb/download/GeoLite2-City.mmdb"

# ---------- TCP-проверка ----------
TCP_CHECK_TIMEOUT = 10
TCP_MAX_WORKERS = 400
MAX_LATENCY_MS = 350

# ---------- TLS-проверка ----------
TLS_CHECK_TIMEOUT = 2
TLS_MAX_WORKERS = 100

# ---------- Реальная проверка через sing-box ----------
SOCKS_BASE_PORT = 10000
SOCKS_PORT_RANGE = 1000
REAL_CHECK_TIMEOUT = 30
REAL_CHECK_CONCURRENCY = 30
SING_BOX_STARTUP_DELAY = 7

# ---------- Тестовые URL ----------
FAST_TEST_URLS = [
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.gstatic.com/generate_204"
]
REAL_SITES = [
    "https://www.google.com/generate_204"
]

# ---------- SPEED TEST ----------
SPEED_TEST_URL = "http://speed.cloudflare.com/__down?bytes=5000000"  # ~5 MB
MIN_SPEED_Mbps = 5  # минимальная скорость для включения
TOP_SPEED_TEST_COUNT = 50  # сколько серверов проверяем на скорость

# =============================================================================
# КОНЕЦ НАСТРОЕК
# =============================================================================

# ---------- НАСТРОЙКА ЛОГИРОВАНИЯ ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

# ---------- СЧЁТЧИКИ ----------
record_counter = 0
current_check = 0
total_checks = 0

# ---------- ЧАСОВОЙ ПОЯС ----------
try:
    from zoneinfo import ZoneInfo
    TIMEZONE = "Asia/Yekaterinburg"
    LOCAL_NOW = datetime.now(ZoneInfo(TIMEZONE))
    logging.info(f"🕐 Используется часовой пояс: {TIMEZONE}")
except ImportError:
    LOCAL_NOW = datetime.utcnow()
    logging.warning("⚠️ zoneinfo не найдена, используется UTC")
TODAY_STR = LOCAL_NOW.strftime("%d-%m-%Y")

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ---------- РАНДОМНЫЙ USER-AGENT ----------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

# ---------- GEOIP ----------
try:
    import geoip2.database
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False
    logging.warning("⚠️ geoip2 не установлена. Флаги стран и города не будут добавлены.")

# ---------- ДИНАМИЧЕСКИЕ ПОРТЫ ----------
_port_counter = 0
_port_lock = threading.Lock()

def get_next_port():
    global _port_counter
    with _port_lock:
        port = SOCKS_BASE_PORT + (_port_counter % SOCKS_PORT_RANGE)
        _port_counter += 1
        return port

# ---------- GEOIP ЗАГРУЗКА ----------
def ensure_geoip_db():
    if not GEOIP_AVAILABLE:
        return False
    if os.path.exists(GEOIP_DB_PATH):
        return True
    logging.info("🌍 Скачиваю базу GeoIP (City)...")
    try:
        r = requests.get(GEOIP_DB_URL, timeout=30, headers={'User-Agent': get_random_ua()})
        r.raise_for_status()
        with open(GEOIP_DB_PATH, 'wb') as f:
            f.write(r.content)
        logging.info("✅ База GeoIP (City) скачана")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка скачивания GeoIP: {e}")
        return False

reader = None
if ensure_geoip_db():
    try:
        reader = geoip2.database.Reader(GEOIP_DB_PATH)
    except Exception as e:
        logging.error(f"❌ Не удалось открыть базу GeoIP: {e}")

def get_geo_info(ip):
    """Возвращает (флаг, город, код страны)"""
    if reader is None:
        return "", "", ""
    try:
        response = reader.city(ip)
        country_code = response.country.iso_code
        city = response.city.name if response.city.name else ""
        flag = ''.join(chr(127397 + ord(c)) for c in country_code.upper()) if country_code else ""
        return flag, city, country_code
    except Exception:
        return "", "", ""

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------
@lru_cache(maxsize=256)
def resolve_host(host):
    return socket.gethostbyname(host)

# ... все остальные функции (read_sources, fetch_content, parse_link и т.д.) остаются без изменений ...

# ---------- НОВАЯ ФУНКЦИЯ SPEED TEST ----------
def check_speed_via_singbox(link, test_url=SPEED_TEST_URL, timeout=20):
    config_dict = parse_link(link)
    if not config_dict:
        return 0

    socks_port = get_next_port()
    sb_config = create_singbox_config(config_dict, socks_port)
    if not sb_config:
        return 0

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        json.dump(sb_config, f)

    process = None
    try:
        process = subprocess.Popen(
            [SING_BOX_PATH, 'run', '-c', config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        time.sleep(SING_BOX_STARTUP_DELAY)

        proxies = {
            'http': f'socks5h://127.0.0.1:{socks_port}',
            'https': f'socks5h://127.0.0.1:{socks_port}'
        }

        start = time.time()
        resp = requests.get(test_url, proxies=proxies, timeout=timeout, stream=True)

        total_bytes = 0
        for chunk in resp.iter_content(chunk_size=8192):
            total_bytes += len(chunk)

        duration = time.time() - start
        if duration == 0:
            return 0

        speed_mbps = (total_bytes * 8) / (duration * 1_000_000)
        return round(speed_mbps, 2)

    except Exception:
        return 0

    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if os.path.exists(config_path):
            os.unlink(config_path)

# ---------- ВСТАВКА SPEED-ТЕСТА В FILTER ----------
def filter_working_links(links):
    global record_counter, current_check, total_checks
    # ... TCP, TLS, REAL проверки остаются без изменений ...
    # working_links_with_geo формируется после REAL проверки

    # ---------- Этап 3: SPEED TEST для топ-50 ----------
    logging.info(f"⚡ Этап 3: Проверка скорости топ-{TOP_SPEED_TEST_COUNT} серверов...")
    working_links_with_speed = []
    for idx, (link, flag, city, country_code) in enumerate(working_links_with_geo[:TOP_SPEED_TEST_COUNT], 1):
        speed = check_speed_via_singbox(link)
        if speed >= MIN_SPEED_Mbps:
            working_links_with_speed.append((link, flag, city, country_code, speed))
            logging.info(f"{idx}/{TOP_SPEED_TEST_COUNT} ✅ {shorten_link(link)} - {speed} Mbps")
        else:
            logging.info(f"{idx}/{TOP_SPEED_TEST_COUNT} ❌ {shorten_link(link)} - скорость {speed} Mbps слишком мала")

    # Заменяем финальный список на новый с SPEED
    working_links_with_geo = working_links_with_speed
    logging.info(f"⚡ SPEED-тест завершён. Всего: {len(working_links_with_geo)} рабочих серверов из {TOP_SPEED_TEST_COUNT}")

    return working_links_with_geo

# ---------- СОХРАНЕНИЕ ----------
def save_working_links(links_with_geo):
    logging.info(f"💾 Сохраняю {len(links_with_geo)} серверов с геоданными...")
    if not links_with_geo:
        logging.warning("Нет серверов для сохранения.")
        return 0

    # Все ссылки уже российские, сортировка не требуется
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"#profile-title:{PROFILE_TITLE}\n")
        f.write(f"#subscription-userinfo:{SUBSCRIPTION_USERINFO}\n")
        f.write(f"#profile-update-interval:{PROFILE_UPDATE_INTERVAL}\n")
        f.write(f"#support-url:{SUPPORT_URL}\n")
        f.write(f"#profile-web-page-url:{PROFILE_WEB_PAGE_URL}\n")
        f.write(f"#announce: АКТИВНЫХ ТОННЕЛЕЙ 🚀 {len(links_with_geo)} | ОБНОВЛЕНО 📅 {TODAY_STR}\n")
        for idx, (link, flag, city, _, speed) in enumerate(links_with_geo, 1):
            link_clean = re.sub(r'#.*$', '', link)
            city_part = f" {city}" if city else ""
            tag = f"#🔑📱ТОННЕЛЬ {idx:04d} | {flag}{city_part} | ⚡ {speed} Mbps |"
            f.write(link_clean + tag + '\n')

    logging.info(f"✅ Сохранено {len(links_with_geo)} серверов в {OUTPUT_FILE}")
    return len(links_with_geo)

# ---------- ГЛАВНАЯ ----------
def main():
    global record_counter, current_check, total_checks
    logging.info("🟢 Запуск генератора подписок (с SPEED-тестом для топ-50)")
    if not check_singbox_available():
        logging.error("sing-box обязателен. Завершение.")
        return

    sources = read_sources()
    if not sources:
        return

    all_links = gather_all_links(sources)
    if not all_links:
        return

    record_counter = 0
    current_check = 0
    total_checks = len(all_links)

    working_links_with_geo = filter_working_links(all_links)
    written = save_working_links(working_links_with_geo)

    if written > 0:
        create_base64_subscription()
    else:
        logging.warning("Нет серверов с флагами – Base64 не создана.")

    logging.info(f"📊 Итог: {len(working_links_with_geo)} рабочих с флагами и скоростью из {len(all_links)} проверенных")
    logging.info("🏁 Работа завершена")

if __name__ == "__main__":
    main()
