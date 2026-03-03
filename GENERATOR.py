#!/usr/bin/env python3
# GENERATOR.py – Расширенная проверка Vless серверов через реальное подключение (Xray-core)

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
import sys
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
XRAY_CORE_PATH = "xray" # Или полный путь к xray, если он не в PATH

# Настройки для REAL-проверки
REAL_CHECK_TIMEOUT = 15     # Максимальное время ожидания ответа от прокси (сек)
REAL_TEST_URL = "http://connectivitycheck.gstatic.com/generate_204"
REAL_CHECK_CONCURRENCY = 3  # Не запускать много реальных проверок одновременно (тяжело для системы)

def read_sources():
    """Читает файл sources.txt, игнорирует пустые строки и комментарии (#)."""
    # ... (функция остается без изменений из предыдущего кода) ...
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
    """Загружает содержимое по URL. Возвращает текст или None при ошибке."""
    # ... (функция остается без изменений из предыдущего кода) ...
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
    """Пытается декодировать строку как base64. Возвращает декодированную строку или оригинал, если не получилось."""
    # ... (функция остается без изменений из предыдущего кода) ...
    try:
        encoded = encoded.strip()
        decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return decoded
    except:
        return encoded

def gather_all_links(sources):
    """Собирает все уникальные Vless-ссылки из всех источников."""
    # ... (функция остается без изменений из предыдущего кода) ...
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
    Возвращает словарь с параметрами или None, если ссылка некорректна.
    """
    try:
        # Убираем vless://
        without_proto = link[8:]
        # Ищем разделитель '@', отделяющий UUID от остальной части
        at_index = without_proto.find('@')
        if at_index == -1:
            return None

        uuid = without_proto[:at_index]
        rest = without_proto[at_index+1:]

        # Парсим оставшуюся часть как URL, чтобы получить host, port, params
        # Для корректного парсинга добавим схему
        parsed = urlparse(f"tcp://{rest}")
        host = parsed.hostname
        port = parsed.port or 443

        # Параметры query
        params = parse_qs(parsed.query)
        # Извлекаем основные параметры, беря первое значение из списка
        config = {
            'uuid': uuid,
            'host': host,
            'port': port,
            'security': params.get('security', ['none'])[0],
            'encryption': params.get('encryption', ['none'])[0],
            'type': params.get('type', ['tcp'])[0],  # network type (tcp, kcp, ws, etc.)
            'sni': params.get('sni', [host])[0],     # Server Name Indication
            'fp': params.get('fp', ['chrome'])[0],   # Fingerprint
            'pbk': params.get('pbk', [''])[0],       # Public key (для reality)
            'sid': params.get('sid', [''])[0],       # Short ID (для reality)
            'spx': params.get('spx', ['/'])[0],      # Service path (для reality)
            'flow': params.get('flow', [''])[0],      # Flow control
            'path': params.get('path', ['/'])[0],     # WebSocket path
            'host_header': params.get('host', [host])[0] # Host header for WS/HTTP
        }
        return config
    except Exception as e:
        logging.debug(f"Ошибка парсинга ссылки {link[:50]}...: {e}")
        return None

def create_xray_config(vless_config):
    """
    Генерирует JSON конфигурацию для Xray-core на основе параметров Vless.
    """
    # Базовая структура конфига
    config = {
        "log": {"loglevel": "error"},
        "inbounds": [
            {
                "port": 1080,  # SOCKS5 прокси на локальном порту
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

    # Настройка streamSettings в зависимости от типа сети и безопасности
    stream = config["outbounds"][0]["streamSettings"]

    # Настройка TLS
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
            "shortId": vless_config['sid']
        }

    # Настройка для WebSocket
    if vless_config['type'] == 'ws':
        stream["wsSettings"] = {
            "path": vless_config['path'],
            "headers": {
                "Host": vless_config['host_header']
            }
        }

    # Можно добавить настройки для gRPC, HTTP/2 и т.д. при необходимости

    return config

def check_vless_real(link):
    """
    РЕАЛЬНАЯ проверка Vless-ссылки через запуск Xray-core.
    Запускает Xray с конфигом, делает запрос через SOCKS5 прокси.
    Возвращает (link, True, latency_ms) если успешно, иначе (link, False, None).
    """
    # Шаг 1: Парсинг ссылки
    vless_config = parse_vless_link(link)
    if not vless_config:
        return (link, False, None)

    # Шаг 2: Создание временного конфиг-файла
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        json.dump(create_xray_config(vless_config), f, indent=2)

    process = None
    start_time = None
    try:
        # Шаг 3: Запуск Xray процесса
        # logging.debug(f"Запуск Xray для {link[:60]}...")
        process = subprocess.Popen(
            [XRAY_CORE_PATH, 'run', '-config', config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Даем Xray время на инициализацию
        time.sleep(1.5)

        # Шаг 4: Проверка через прокси
        proxies = {
            'http': 'socks5h://127.0.0.1:1080',
            'https': 'socks5h://127.0.0.1:1080'
        }
        start_time = time.time()
        response = requests.get(
            REAL_TEST_URL,
            proxies=proxies,
            timeout=REAL_CHECK_TIMEOUT,
            headers={'User-Agent': USER_AGENT}
        )
        latency = int((time.time() - start_time) * 1000)  # в миллисекундах

        if response.status_code == 204:
            return (link, True, latency)
        else:
            return (link, False, None)

    except requests.exceptions.RequestException as e:
        logging.debug(f"Ошибка подключения через прокси: {e}")
        return (link, False, None)
    except Exception as e:
        logging.debug(f"Неожиданная ошибка при проверке {link[:60]}...: {e}")
        return (link, False, None)
    finally:
        # Шаг 5: Завершение процесса Xray и удаление временного файла
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if os.path.exists(config_path):
            os.unlink(config_path)

def filter_working_links(links, use_real_check=True):
    """
    Проверяет список ссылок и возвращает только рабочие.
    Если use_real_check=True, использует реальную проверку через Xray.
    Иначе использует быструю TCP-проверку.
    """
    working = []
    total = len(links)
    checked = 0

    if use_real_check:
        logging.info("🧪 Запуск РЕАЛЬНОЙ проверки через Xray-core...")
        # Для реальной проверки ограничим количество одновременных процессов
        with ThreadPoolExecutor(max_workers=REAL_CHECK_CONCURRENCY) as executor:
            future_to_link = {executor.submit(check_vless_real, link): link for link in links}
            for future in as_completed(future_to_link):
                link, is_working, latency = future.result()
                checked += 1
                if is_working:
                    working.append(link)
                    logging.info(f"✅ [{checked}/{total}] Работает (latency: {latency}ms): {link[:80]}...")
                else:
                    logging.info(f"❌ [{checked}/{total}] Не работает: {link[:80]}...")
    else:
        logging.info("🌐 Запуск БЫСТРОЙ TCP-проверки...")
        def check_tcp(link):
            # Быстрая TCP проверка (код из предыдущей версии)
            try:
                parsed = urlparse(link[8:] if link.startswith('vless://') else link)
                if not parsed.hostname:
                    return (link, False)
                port = parsed.port or 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((parsed.hostname, port))
                sock.close()
                return (link, result == 0)
            except:
                return (link, False)

        with ThreadPoolExecutor(max_workers=50) as executor:
            future_to_link = {executor.submit(check_tcp, link): link for link in links}
            for future in as_completed(future_to_link):
                link, is_working = future.result()
                checked += 1
                if is_working:
                    working.append(link)
                    logging.info(f"✅ [{checked}/{total}] TCP OK: {link[:80]}...")
                else:
                    logging.info(f"❌ [{checked}/{total}] TCP Failed: {link[:80]}...")

    return working

def save_working_links(links):
    """Сохраняет рабочие ссылки в OUTPUT_FILE, по одной на строку."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(link + '\n')
    logging.info(f"💾 Сохранено {len(links)} рабочих ссылок в {OUTPUT_FILE}")

def check_xray_available():
    """Проверяет, доступен ли Xray-core в системе."""
    try:
        result = subprocess.run([XRAY_CORE_PATH, '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logging.info(f"✅ Xray-core найден: {result.stdout.splitlines()[0] if result.stdout else 'версия неизвестна'}")
            return True
        else:
            logging.warning("⚠️ Xray-core не отвечает на запрос версии")
            return False
    except FileNotFoundError:
        logging.error(f"❌ Xray-core не найден по пути '{XRAY_CORE_PATH}'. Установите Xray-core и добавьте в PATH.")
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка при проверке Xray-core: {e}")
        return False

def main():
    # Проверяем наличие Xray-core (но не прерываем работу, можно использовать TCP fallback)
    xray_available = check_xray_available()

    sources = read_sources()
    if not sources:
        logging.error("Нет источников для обработки.")
        return

    all_links = gather_all_links(sources)
    if not all_links:
        logging.warning("Не найдено ни одной Vless-ссылки.")
        return

    # Выбор метода проверки
    use_real = xray_available  # Если Xray есть, используем реальную проверку
    if not use_real:
        logging.warning("⚠️ Будет использована ТОЛЬКО TCP-проверка (менее точная)")

    working_links = filter_working_links(all_links, use_real_check=use_real)
    save_working_links(working_links)

    # Небольшая статистика
    logging.info(f"📊 Итог: {len(working_links)} рабочих из {len(all_links)} проверенных")

if __name__ == "__main__":
    main()
