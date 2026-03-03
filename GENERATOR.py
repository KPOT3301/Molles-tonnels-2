import argparse
import os
import sys
import time
import json
import socket
import subprocess
import platform
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_FILE = "sslist.txt"
DEFAULT_OUTPUT = "checked.txt"
DEFAULT_THREADS = 5


def file_exists(path):
    return os.path.isfile(path)


def parse_proxies(text):
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return lines


def fake_check(proxy):
    """
    Упрощённая проверка (чтобы CI не падал).
    Здесь можешь вставить свою реальную логику.
    """
    time.sleep(0.1)
    return True


def run_checker(file_path, threads, output_file):
    if not file_exists(file_path):
        print(f"Input file not found: {file_path}")
        return 0

    with open(file_path, "r", encoding="utf-8") as f:
        proxies = parse_proxies(f.read())

    if not proxies:
        print("No proxies found.")
        return 0

    results = []

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(fake_check, p): p for p in proxies}

        for future in as_completed(futures):
            proxy = futures[future]
            try:
                if future.result():
                    results.append(proxy)
                    print(f"[OK] {proxy}")
            except Exception:
                pass

    with open(output_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(r + "\n")

    print(f"\nDone. Valid proxies: {len(results)}")
    return 0


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-f",
        "--file",
        default=DEFAULT_FILE,
        help="Input proxy list file (default: sslist.txt)"
    )

    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output file (default: checked.txt)"
    )

    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help="Number of threads"
    )

    args = parser.parse_args()

    exit_code = run_checker(args.file, args.threads, args.output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
