import argparse
import sys
import os
import shutil
import json
import time
import socket
import subprocess
import platform
import base64
import requests
import psutil
import re
import stat
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

urllib3_disable = False
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    urllib3_disable = True
except:
    pass

TEMP_DIR = os.path.abspath("temp")
os.makedirs(TEMP_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "core_path": "xray",
    "threads": 5,
    "timeout": 3,
    "local_port_start": 10000,
    "test_domain": "http://cp.cloudflare.com/generate_204",
    "output_file": "checked.txt",
    "core_startup_timeout": 3,
    "core_kill_delay": 0.1
}

PROTO_HINTS = ("vless://", "vmess://", "trojan://", "ss://")
URL_FINDER = re.compile(r'(?:vless|vmess|trojan|ss)://[^\s]+', re.IGNORECASE)

def clean_url(url):
    return url.strip().replace('\ufeff', '').replace('\u200b', '')

def parse_content(text):
    results = set()
    matches = URL_FINDER.findall(text)
    for m in matches:
        u = clean_url(m)
        if len(u) > 10:
            results.add(u)
    return list(results)

def is_port_open(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except:
        return False

def wait_core(port, timeout):
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.1)
    return False

def run_core(core_path, config_path):
    if platform.system() != "Windows":
        st = os.stat(core_path)
        os.chmod(core_path, st.st_mode | stat.S_IXEXEC)

    cmd = [core_path, "run", "-c", config_path]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def kill_core(proc):
    try:
        proc.kill()
    except:
        pass

def check_proxy(port, domain, timeout):
    proxies = {
        "http": f"socks5://127.0.0.1:{port}",
        "https": f"socks5://127.0.0.1:{port}"
    }
    try:
        start = time.time()
        r = requests.get(domain, proxies=proxies, timeout=timeout)
        if r.status_code < 400:
            return round((time.time() - start) * 1000)
    except:
        return None
    return None

def create_config(proxy, port):
    config = {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "port": port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False}
        }],
        "outbounds": [{
            "protocol": "freedom",
            "settings": {}
        }]
    }

    path = os.path.join(TEMP_DIR, f"cfg_{port}.json")
    with open(path, "w") as f:
        json.dump(config, f)

    return path

def checker_worker(proxy, port, args):
    cfg = create_config(proxy, port)
    proc = run_core(args.core, cfg)

    if not wait_core(port, args.t2exec):
        kill_core(proc)
        return None

    ping = check_proxy(port, args.domain, args.timeout)

    kill_core(proc)
    time.sleep(args.t2kill)

    if ping:
        return (proxy, ping)

    return None

def run_logic(args):
    if not os.path.exists(args.file):
        print("File not found")
        return

    with open(args.file, "r", encoding="utf-8") as f:
        proxies = parse_content(f.read())

    if not proxies:
        print("No proxies found")
        return

    results = []
    port = args.lport

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = []
        for p in proxies:
            futures.append(executor.submit(checker_worker, p, port, args))
            port += 1

        for f in as_completed(futures):
            r = f.result()
            if r:
                print(f"[LIVE] {r[1]} ms")
                results.append(r)

    results.sort(key=lambda x: x[1])

    with open(args.output, "w") as f:
        for r in results:
            f.write(r[0] + "\n")

    print(f"\nDone. Working proxies: {len(results)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    parser.add_argument("-c", "--core", default=DEFAULT_CONFIG["core_path"])
    parser.add_argument("-t", "--timeout", type=int, default=DEFAULT_CONFIG["timeout"])
    parser.add_argument("-l", "--lport", type=int, default=DEFAULT_CONFIG["local_port_start"])
    parser.add_argument("-T", "--threads", type=int, default=DEFAULT_CONFIG["threads"])
    parser.add_argument("-o", "--output", default=DEFAULT_CONFIG["output_file"])
    parser.add_argument("-d", "--domain", default=DEFAULT_CONFIG["test_domain"])
    parser.add_argument("--t2exec", type=float, default=DEFAULT_CONFIG["core_startup_timeout"])
    parser.add_argument("--t2kill", type=float, default=DEFAULT_CONFIG["core_kill_delay"])

    args = parser.parse_args()
    run_logic(args)

if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
