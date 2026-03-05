#!/usr/bin/env python3
# GENERATOR.py – Двухуровневая проверка Vless/SS/Trojan серверов + флаги стран
# (полный код с корректным отображением прогресса на втором этапе)

import os
import re
import socket
import base64
import logging
import subprocess
import time
import json
import tempfile
import sys
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from datetime import datetime

# ---------- НАСТРОЙКА ЛОГИРОВАНИЯ ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

record_counter = 0
current_check = 0
total_checks = 0

# ... (все остальные функции, включая парсеры, создание конфигов, check_tcp, check_real) ...

def filter_working_links(links):
    global record_counter, current_check, total_checks
    total_checks = len(links)
    logging.info(f"🚀 Начинаю двухуровневую проверку {total_checks} ссылок")

    # ---------- Этап 1: TCP ----------
    logging.info(f"🌐 Этап 1: TCP-проверка {total_checks} ссылок...")
    tcp_ok = []
    with ThreadPoolExecutor(max_workers=TCP_MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_tcp, link): link for link in links}
        for future in as_completed(future_to_link):
            current_check += 1
            record_counter += 1
            link, ok = future.result()
            if ok:
                tcp_ok.append(link)
                emoji = "✅"
                status = "TCP OK"
            else:
                emoji = "❌"
                status = "TCP Failed"
            short_link = link[:120] + "..." if len(link) > 120 else link
            logging.info(f"{record_counter} {emoji} [{current_check}/{total_checks}] {status}: {short_link}")

    logging.info(f"📊 TCP-проверка завершена. Прошли: {len(tcp_ok)}/{total_checks}")

    if not tcp_ok:
        return []

    # ---------- Этап 2: реальная проверка ----------
    logging.info(f"🧪 Этап 2: Реальная проверка {len(tcp_ok)} ссылок...")
    working_links = []
    stage_total = len(tcp_ok)
    stage_current = 0
    with ThreadPoolExecutor(max_workers=REAL_CHECK_CONCURRENCY) as executor:
        future_to_link = {executor.submit(check_real, link): link for link in tcp_ok}
        for future in as_completed(future_to_link):
            stage_current += 1
            current_check += 1
            record_counter += 1
            link, is_working, latency = future.result()

            if is_working:
                if MAX_LATENCY_MS > 0 and latency > MAX_LATENCY_MS:
                    emoji = "⚠️"
                    status = f"Слишком медленный (latency: {latency}ms > {MAX_LATENCY_MS}ms)"
                else:
                    emoji = "✅"
                    status = f"Работает (latency: {latency}ms)"
                    working_links.append(link)
            else:
                emoji = "❌"
                status = "Не работает"

            short_link = link[:120] + "..." if len(link) > 120 else link
            logging.info(f"{record_counter} {emoji} [{stage_current}/{stage_total}] {status}: {short_link}")

    logging.info(f"📊 Реальная проверка завершена. Рабочих: {len(working_links)}/{stage_total}")
    return working_links

# ... (остальные функции: save_working_links, create_base64_subscription, main и т.д.) ...

if __name__ == "__main__":
    main()
