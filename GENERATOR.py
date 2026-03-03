#!/usr/bin/env python3
# GENERATOR.py – Оптимизированная проверка Vless серверов (двухэтапная, порт 8080)

import re
import socket
import base64
import logging
import subprocess
import time
import json
import tempfile
import os
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import requests

# Настройка логирования – пока оставим DEBUG для диагностики
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Константы
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "subscription.txt"
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
XRAY_CORE_PATH = "xray"

# Ускоренная TCP-проверка
TCP_CHECK_TIMEOUT = 2
TCP_MAX_WORKERS = 300

# Реальная проверка – порт изменён на 8080
SOCKS_PORT = 8080
REAL_CHECK_TIMEOUT = 15
REAL_CHECK_CONCURRENCY = 9
XRAY_STARTUP_DELAY = 3          # увеличено для надёжности
RETRY_COUNT = 1

# Список тестовых URL (возвращают 204)
TEST_URLS = [
    "http://connectivitycheck.gstatic.com/generate_204",
    "https://connectivitycheck.gstatic.com/generate_204",
    "http://cp.cloudflare.com/generate_204",
    "http://www.gstatic.com/generate_204",
    "http://www.google.com/generate_204"
]

# Режим работы: True – только TCP (быстро), False – полная проверка
ONLY_TCP = False

@lru_cache(maxsize=256)
def resolve_host(host):
    """Кэширует IP-адрес по имени хоста."""
    return socket.gethostbyname(host)

def read_sources():
    sources = []
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    sources.append(line)
        logging.info(f"📚 Загружено {len(sources)} источников")
    except FileNotFoundError:
        logging.error(f"❌ Файл {SOURCES_FILE} не найден")
    return sources

def fetch_content(url):
    try:
        headers = {'User-Agent': USER_AGENT}
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logging.warning(f"⚠️ Не удалось загрузить {url}: {e}")
        return None

def extract_vless_links_from_text(text):
    return re.findall(r'vless://[^\s<>"\']+', text)

def decode_base64_content(encoded):
    try:
        encoded = encoded.strip()
        decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return decoded
    except:
        return encoded

def gather_all_links(sources):
    all_links = set()
    for src in sources:
        if src.startswith('vless://'):
            all_links.add(src)
            continue

        content = fetch_content(src)
        if not content:
            continue

        decoded = decode_base64_content(content)
        links = extract_vless_links_from_text(content)
        if decoded != content:
            links.extend(extract_vless_links_from_text(decoded))

        for link in links:
            all_links.add(link)

        logging.info(f"🔗 Из {src} получено {len(links)} ссылок")

    logging.info(f"🎯 Всего собрано уникальных Vless-ссылок: {len(all_links)}")
    return list(all_links)

def parse_vless_link(link):
    try:
        without_proto = link[8:]
        at_index = without_proto.find('@')
        if at_index == -1:
            return None

        uuid = without_proto[:at_index]
        rest = without_proto[at_index+1:]

        parsed = urlparse(f"tcp://{rest}")
        host = parsed.hostname
        port = parsed.port or 443

        params = parse_qs(parsed.query)
        security = params.get('security', ['none'])[0]
        # Нормализация опечатки tsl -> tls
        if security == 'tsl':
            security = 'tls'
            logging.debug(f"Нормализовано security: tsl -> tls для {link[:60]}")
        # Для reality тоже может быть опечатка, но оставим как есть

        config = {
            'uuid': uuid,
            'host': host,
            'port': port,
            'security': security,
            'encryption': params.get('encryption', ['none'])[0],
            'type': params.get('type', ['tcp'])[0],
            'sni': params.get('sni', [host])[0],
            'fp': params.get('fp', ['chrome'])[0],
            'pbk': params.get('pbk', [''])[0],
            'sid': params.get('sid', [''])[0],
            'spx': params.get('spx', ['/'])[0],
            'flow': params.get('flow', [''])[0],
            'path': params.get('path', ['/'])[0],
            'host_header': params.get('host', [host])[0]
        }
        logging.debug(f"Парсинг ссылки {link[:60]}... -> {config}")
        return config
    except Exception as e:
        logging.debug(f"Ошибка парсинга ссылки {link[:50]}...: {e}")
        return None

def create_xray_config(vless_config):
    """Генерирует JSON конфигурацию для Xray-core с портом 8080."""
    config = {
        "log": {"loglevel": "error"},
        "inbounds": [
            {
                "port": SOCKS_PORT,          # изменено на 8080
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True,
                    "ip": "127.0.0.1"
                }
            }
        ],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": vless_config['host'],
                            "port": vless_config['port'],
                            "users": [
                                {
                                    "id": vless_config['uuid'],
                                    "encryption": vless_config['encryption'],
                                    "flow": vless_config['flow']
                                }
                            ]
                        }
                    ]
                },
                "streamSettings": {
                    "network": vless_config['type'],
                    "security": vless_config['security']
                }
            }
        ]
    }

    stream = config["outbounds"][0]["streamSettings"]

    if vless_config['security'] == 'tls':
        stream["tlsSettings"] = {
            "serverName": vless_config['sni'],
            "fingerprint": vless_config['fp'],
            "allowInsecure": False
        }
    elif vless_config['security'] == 'reality':
        stream["realitySettings"] = {
            "serverName": vless_config['sni'],
            "fingerprint": vless_config['fp'],
            "publicKey": vless_config['pbk'],
            "shortId": vless_config['sid'],
            "spiderX": vless_config['spx']
        }

    if vless_config['type'] == 'ws':
        stream["wsSettings"] = {
            "path": vless_config['path'],
            "headers": {
                "Host": vless_config['host_header']
            }
        }

    return config

def check_tcp(link):
    parsed = parse_vless_link(link)
    if not parsed:
        return (link, False)
    host = parsed['host']
    port = parsed['port']
    try:
        ip = resolve_host(host)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TCP_CHECK_TIMEOUT)
        result = sock.connect_ex((ip, port))
        sock.close()
        return (link, result == 0)
    except Exception as e:
        logging.debug(f"TCP ошибка для {link[:60]}: {e}")
        return (link, False)

def check_vless_real(link):
    vless_config = parse_vless_link(link)
    if not vless_config:
        return (link, False, None)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        json.dump(create_xray_config(vless_config), f, indent=2)

    process = None
    try:
        process = subprocess.Popen(
            [XRAY_CORE_PATH, 'run', '-config', config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        time.sleep(XRAY_STARTUP_DELAY)

        # Проверка, что порт 8080 открыт
        sock_check = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sock_check.connect_ex(('127.0.0.1', SOCKS_PORT)) != 0:
            logging.debug(f"Порт {SOCKS_PORT} не открыт после запуска Xray")
        sock_check.close()

        proxies = {
            'http': f'socks5h://127.0.0.1:{SOCKS_PORT}',
            'https': f'socks5h://127.0.0.1:{SOCKS_PORT}'
        }

        # Перебираем тестовые URL
        for test_url in TEST_URLS:
            for attempt in range(RETRY_COUNT + 1):
                try:
                    start_time = time.time()
                    response = requests.get(
                        test_url,
                        proxies=proxies,
                        timeout=REAL_CHECK_TIMEOUT,
                        headers={'User-Agent': USER_AGENT},
                        allow_redirects=False
                    )
                    latency = int((time.time() - start_time) * 1000)

                    if response.status_code == 204:
                        return (link, True, latency)
                    else:
                        logging.debug(f"URL {test_url} вернул {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logging.debug(f"Попытка {attempt+1} для {test_url} не удалась: {e}")
                    time.sleep(1)

        # Если все попытки провалились, читаем stderr Xray
        if process:
            stdout, stderr = process.communicate(timeout=2)
            if stderr:
                logging.info(f"Xray stderr для {link[:60]}: {stderr[:1000]}")
            else:
                logging.debug("Xray stderr пуст")
        return (link, False, None)

    except Exception as e:
        logging.debug(f"Ошибка при проверке {link[:60]}...: {e}")
        return (link, False, None)
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if os.path.exists(config_path):
            os.unlink(config_path)

def filter_working_links(links):
    total = len(links)

    # Этап 1: TCP-проверка всех ссылок
    logging.info(f"🌐 Этап 1: TCP-проверка {total} ссылок (параллельность {TCP_MAX_WORKERS}, таймаут {TCP_CHECK_TIMEOUT}с)...")
    tcp_ok = []
    with ThreadPoolExecutor(max_workers=TCP_MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_tcp, link): link for link in links}
        for i, future in enumerate(as_completed(future_to_link), 1):
            link, ok = future.result()
            if ok:
                tcp_ok.append(link)
                logging.info(f"✅ TCP OK [{i}/{total}]: {link[:80]}...")
            else:
                logging.info(f"❌ TCP Failed [{i}/{total}]: {link[:80]}...")

    logging.info(f"📊 TCP-проверка завершена. Прошли: {len(tcp_ok)}/{total}")

    if ONLY_TCP:
        logging.info("⚡ Режим ONLY_TCP: возвращаем результаты TCP-проверки.")
        return tcp_ok

    if not tcp_ok:
        logging.warning("⚠️ Нет ссылок, прошедших TCP. Реальная проверка не требуется.")
        return []

    # Этап 2: реальная проверка только для прошедших TCP
    logging.info(f"🧪 Этап 2: Реальная проверка {len(tcp_ok)} ссылок через Xray-core (порт {SOCKS_PORT}, параллельность {REAL_CHECK_CONCURRENCY})...")
    working_real = []
    with ThreadPoolExecutor(max_workers=REAL_CHECK_CONCURRENCY) as executor:
        future_to_link = {executor.submit(check_vless_real, link): link for link in tcp_ok}
        for i, future in enumerate(as_completed(future_to_link), 1):
            link, is_working, latency = future.result()
            if is_working:
                working_real.append(link)
                logging.info(f"✅ [{i}/{len(tcp_ok)}] Работает (latency: {latency}ms): {link[:80]}...")
            else:
                logging.info(f"❌ [{i}/{len(tcp_ok)}] Не работает: {link[:80]}...")

    return working_real

def save_working_links(links):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(link + '\n')
    logging.info(f"💾 Сохранено {len(links)} рабочих ссылок в {OUTPUT_FILE}")

def check_xray_available():
    try:
        result = subprocess.run([XRAY_CORE_PATH, '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logging.info(f"✅ Xray-core найден: {result.stdout.splitlines()[0]}")
            return True
        else:
            logging.warning("⚠️ Xray-core не отвечает")
            return False
    except FileNotFoundError:
        logging.error(f"❌ Xray-core не найден по пути '{XRAY_CORE_PATH}'")
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка при проверке Xray-core: {e}")
        return False

def main():
    if not check_xray_available():
        logging.error("Xray-core обязателен. Завершение.")
        return

    sources = read_sources()
    if not sources:
        return

    all_links = gather_all_links(sources)
    if not all_links:
        return

    working_links = filter_working_links(all_links)
    save_working_links(working_links)

    logging.info(f"📊 Итог: {len(working_links)} рабочих из {len(all_links)} проверенных")

if __name__ == "__main__":
    main()
