#!/usr/bin/env python3
# GENERATOR.py – Проверка Vless серверов через библиотеку python-v2ray

import re
import base64
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from python_v2ray.tester import ConnectionTester

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Константы
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "subscription.txt"
REQUEST_TIMEOUT = 10
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
        logging.info(f"📚 Загружено {len(sources)} источников")
    except FileNotFoundError:
        logging.error(f"❌ Файл {SOURCES_FILE} не найден")
    return sources

def fetch_content(url):
    """Загружает содержимое по URL. Возвращает текст или None при ошибке."""
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
    try:
        encoded = encoded.strip()
        decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return decoded
    except:
        return encoded

def gather_all_links(sources):
    """Собирает все уникальные Vless-ссылки из всех источников."""
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

def filter_working_links(links):
    """
    Проверяет список ссылок через библиотеку python-v2ray (реальное подключение).
    Возвращает список рабочих ссылок.
    """
    if not links:
        return []

    logging.info("🧪 Запуск проверки через python-v2ray...")

    # Создаём временную директорию, куда библиотека скачает Xray-core
    with tempfile.TemporaryDirectory() as tmpdir:
        vendor = os.path.join(tmpdir, 'vendor')
        core = os.path.join(tmpdir, 'core_engine')
        # Инициализируем тестер
        tester = ConnectionTester(vendor_path=vendor, core_engine_path=core)

        # Запускаем проверку всех ссылок
        # Библиотека сама управляет параллельностью (по умолчанию до 10 одновременных)
        results = tester.test_uris(links)

    # Обрабатываем результаты
    working = []
    total = len(results)
    for i, res in enumerate(results, 1):
        uri = res.get('uri', 'unknown')
        status = res.get('status')
        ping = res.get('ping_ms')
        error = res.get('error', '')

        if status == 'success':
            working.append(uri)
            logging.info(f"✅ [{i}/{total}] Работает (ping: {ping} ms): {uri[:80]}...")
        else:
            logging.info(f"❌ [{i}/{total}] Не работает: {uri[:80]}... Причина: {error}")

    return working

def save_working_links(links):
    """Сохраняет рабочие ссылки в OUTPUT_FILE, по одной на строку."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(link + '\n')
    logging.info(f"💾 Сохранено {len(links)} рабочих ссылок в {OUTPUT_FILE}")

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

    logging.info(f"📊 Итог: {len(working_links)} рабочих из {len(all_links)} проверенных")

if __name__ == "__main__":
    main()
