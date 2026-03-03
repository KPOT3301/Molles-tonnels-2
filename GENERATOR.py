#!/usr/bin/env python3
# GENERATOR.py – Расширенная проверка Vless серверов через реальное подключение (Xray-core)
# Версия с улучшенной диагностикой и повторными попытками

import re
import socket
import base64
import logging
import subprocess
import time
import json
import tempfile
import os
import signal
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Константы
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "subscription.txt"
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
XRAY_CORE_PATH = "xray"  # предполагается, что xray в PATH

# Настройки для REAL-проверки
REAL_CHECK_TIMEOUT = 20          # увеличенный таймаут
REAL_CHECK_CONCURRENCY = 3       # одновременных проверок
XRAY_STARTUP_DELAY = 3           # секунд на запуск Xray
TEST_URL = "http://connectivitycheck.gstatic.com/generate_204"
RETRY_COUNT = 2                  # повторные попытки запроса

def read_sources():
    """Читает файл sources.txt."""
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
    """Загружает содержимое по URL."""
    try:
        headers = {'User-Agent': USER_AGENT}
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logging.warning(f"⚠️ Не удалось загрузить {url}: {e}")
        return None

def extract_vless_links_from_text(text):
    """Извлекает все ссылки vless:// из текста."""
    return re.findall(r'vless://[^\s<>"\']+', text)

def decode_base64_content(encoded):
    """Декодирует base64, если возможно."""
    try:
        encoded = encoded.strip()
        decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return decoded
    except:
        return encoded

def gather_all_links(sources):
    """Собирает все уникальные Vless-ссылки."""
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
    """
    Парсит vless:// ссылку и извлекает параметры.
    Возвращает словарь или None.
    """
    try:
        # Убираем vless://
        without_proto = link[8:]
        at_index = without_proto.find('@')
        if at_index == -1:
            return None

        uuid = without_proto[:at_index]
        rest = without_proto[at_index+1:]

        # Для парсинга добавим схему
        parsed = urlparse(f"tcp://{rest}")
        host = parsed.hostname
        port = parsed.port or 443

        params = parse_qs(parsed.query)
        config = {
            'uuid': uuid,
            'host': host,
            'port': port,
            'security': params.get('security', ['none'])[0],
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
        return config
    except Exception as e:
        logging.debug(f"Ошибка парсинга ссылки {link[:50]}...: {e}")
        return None

def create_xray_config(vless_config):
    """
    Генерирует JSON конфигурацию для Xray-core.
    """
    config = {
        "log": {"loglevel": "error"},  # при отладке можно сменить на debug
        "inbounds": [
            {
                "port": 1080,
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

    # TLS
    if vless_config['security'] == 'tls':
        stream["tlsSettings"] = {
            "serverName": vless_config['sni'],
            "fingerprint": vless_config['fp'],
            "allowInsecure": False
        }
    # Reality
    elif vless_config['security'] == 'reality':
        stream["realitySettings"] = {
            "serverName": vless_config['sni'],
            "fingerprint": vless_config['fp'],
            "publicKey": vless_config['pbk'],
            "shortId": vless_config['sid'],
            "spiderX": vless_config['spx']   # иногда нужно
        }

    # WebSocket
    if vless_config['type'] == 'ws':
        stream["wsSettings"] = {
            "path": vless_config['path'],
            "headers": {
                "Host": vless_config['host_header']
            }
        }

    # gRPC, HTTP/2 можно добавить при необходимости

    return config

def check_vless_real(link):
    """
    Проверяет Vless-ссылку через запуск Xray-core.
    Возвращает (link, True, latency_ms) если успешно, иначе (link, False, None).
    """
    vless_config = parse_vless_link(link)
    if not vless_config:
        return (link, False, None)

    # Для отладки выведем параметры первой ссылки
    logging.debug(f"Парсинг ссылки: {vless_config}")

    # Создаём временный конфиг
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        json.dump(create_xray_config(vless_config), f, indent=2)

    process = None
    try:
        # Запускаем Xray с этим конфигом
        process = subprocess.Popen(
            [XRAY_CORE_PATH, 'run', '-config', config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Даём время на инициализацию
        time.sleep(XRAY_STARTUP_DELAY)

        # Настройки прокси
        proxies = {
            'http': 'socks5h://127.0.0.1:1080',
            'https': 'socks5h://127.0.0.1:1080'
        }

        # Несколько попыток запроса
        for attempt in range(RETRY_COUNT + 1):
            try:
                start_time = time.time()
                response = requests.get(
                    TEST_URL,
                    proxies=proxies,
                    timeout=REAL_CHECK_TIMEOUT,
                    headers={'User-Agent': USER_AGENT}
                )
                latency = int((time.time() - start_time) * 1000)

                if response.status_code == 204:
                    # Успех
                    return (link, True, latency)
                else:
                    logging.debug(f"Неожиданный статус: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logging.debug(f"Попытка {attempt+1} не удалась: {e}")
                time.sleep(1)  # пауза перед повтором

        # Если все попытки провалились, читаем stderr Xray для диагностики
        if process:
            stdout, stderr = process.communicate(timeout=2)
            if stderr:
                # Обрежем, чтобы не засорять лог
                logging.debug(f"Xray stderr: {stderr[:500]}")
        return (link, False, None)

    except Exception as e:
        logging.debug(f"Ошибка при проверке {link[:60]}...: {e}")
        return (link, False, None)
    finally:
        # Завершаем процесс Xray
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        # Удаляем временный файл
        if os.path.exists(config_path):
            os.unlink(config_path)

def filter_working_links(links):
    """Проверяет ссылки параллельно и возвращает только рабочие."""
    working = []
    total = len(links)
    logging.info(f"🧪 Запуск РЕАЛЬНОЙ проверки через Xray-core (параллельность {REAL_CHECK_CONCURRENCY})...")

    with ThreadPoolExecutor(max_workers=REAL_CHECK_CONCURRENCY) as executor:
        future_to_link = {executor.submit(check_vless_real, link): link for link in links}
        for i, future in enumerate(as_completed(future_to_link), 1):
            link, is_working, latency = future.result()
            if is_working:
                working.append(link)
                logging.info(f"✅ [{i}/{total}] Работает (latency: {latency}ms): {link[:80]}...")
            else:
                logging.info(f"❌ [{i}/{total}] Не работает: {link[:80]}...")

    return working

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
        logging.error("Xray-core обязателен для работы. Завершение.")
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
