#!/usr/bin/env python3
# GENERATOR.py – проверка Vless серверов из списка источников

import re
import socket
import base64
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Константы
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "subscription.txt"
CHECK_TIMEOUT = 5          # таймаут TCP-проверки (сек)
MAX_THREADS = 50           # количество потоков при проверке
REQUEST_TIMEOUT = 10       # таймаут HTTP-запроса
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def read_sources():
    """Читает файл sources.txt, игнорирует пустые строки и комментарии (#)."""
    sources = []
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    sources.append(line)
        logging.info(f"Загружено {len(sources)} источников")
    except FileNotFoundError:
        logging.error(f"Файл {SOURCES_FILE} не найден")
    return sources

def fetch_content(url):
    """Загружает содержимое по URL. Возвращает текст или None при ошибке."""
    try:
        headers = {'User-Agent': USER_AGENT}
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logging.warning(f"Не удалось загрузить {url}: {e}")
        return None

def extract_vless_links_from_text(text):
    """Извлекает все ссылки vless:// из текста."""
    return re.findall(r'vless://[^\s<>"\']+', text)

def decode_base64_content(encoded):
    """Пытается декодировать строку как base64. Возвращает декодированную строку или оригинал, если не получилось."""
    try:
        # Удаляем возможные пробельные символы
        encoded = encoded.strip()
        decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return decoded
    except:
        return encoded  # не base64, возвращаем как есть

def gather_all_links(sources):
    """Собирает все уникальные Vless-ссылки из всех источников."""
    all_links = set()
    for src in sources:
        # Если сама строка является vless-ссылкой, добавляем её
        if src.startswith('vless://'):
            all_links.add(src)
            continue

        # Иначе считаем, что это URL подписки
        content = fetch_content(src)
        if not content:
            continue

        # Пробуем декодировать как base64 (часто подписки кодированы)
        decoded = decode_base64_content(content)

        # Ищем ссылки в оригинальном и декодированном содержимом
        links = extract_vless_links_from_text(content)
        if decoded != content:
            links.extend(extract_vless_links_from_text(decoded))

        for link in links:
            all_links.add(link)

        logging.info(f"Из {src} получено {len(links)} ссылок")

    logging.info(f"Всего собрано уникальных Vless-ссылок: {len(all_links)}")
    return list(all_links)

def check_vless_link(link):
    """
    Проверяет работоспособность Vless-ссылки.
    Пытается установить TCP-соединение с хостом и портом, указанными в ссылке.
    Возвращает (link, True) если успешно, иначе (link, False).
    """
    try:
        # Парсим URL
        parsed = urlparse(link)
        if not parsed.hostname:
            return (link, False)

        # Порт по умолчанию для vless – 443, но обычно он явно указан
        port = parsed.port or 443

        # Проверка TCP-соединения
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CHECK_TIMEOUT)
        result = sock.connect_ex((parsed.hostname, port))
        sock.close()

        if result == 0:
            return (link, True)
        else:
            return (link, False)
    except Exception as e:
        logging.debug(f"Ошибка при проверке {link}: {e}")
        return (link, False)

def filter_working_links(links):
    """Проверяет список ссылок параллельно и возвращает только рабочие."""
    working = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_link = {executor.submit(check_vless_link, link): link for link in links}
        for future in as_completed(future_to_link):
            link, is_working = future.result()
            if is_working:
                working.append(link)
                logging.info(f"✅ Работает: {link[:60]}...")
            else:
                logging.info(f"❌ Не работает: {link[:60]}...")
    return working

def save_working_links(links):
    """Сохраняет рабочие ссылки в OUTPUT_FILE, по одной на строку."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(link + '\n')
    logging.info(f"Сохранено {len(links)} рабочих ссылок в {OUTPUT_FILE}")

def main():
    sources = read_sources()
    if not sources:
        logging.error("Нет источников для обработки.")
        return

    all_links = gather_all_links(sources)
    if not all_links:
        logging.warning("Не найдено ни одной Vless-ссылки.")
        return

    working_links = filter_working_links(all_links)
    save_working_links(working_links)

if __name__ == "__main__":
    main()
