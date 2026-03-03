import os, requests, base64, json, subprocess, stat, time, socket, datetime

INPUT_FILE = 'links.txt'
OUTPUT_FILE = 'subscription.txt'
CHECKER_URL = "https://github.com/nndrizhu/nodes-checker/releases/latest/download/nodes-checker-linux-amd64"
CHECKER_PATH = "./nodes-checker"
BATCH_SIZE = 100 

def download_checker():
    if not os.path.exists(CHECKER_PATH):
        r = requests.get(CHECKER_URL)
        with open(CHECKER_PATH, "wb") as f: f.write(r.content)
        os.chmod(CHECKER_PATH, os.stat(CHECKER_PATH).st_mode | stat.S_IEXEC)

def parse_host(link):
    try:
        if link.startswith('vless://'): return link.split('@')[1].split(':')[0]
        if link.startswith('vmess://'): 
            return json.loads(base64.b64decode(link[8:]).decode('utf-8')).get('add')
    except: return None

def get_batch_ip_info(hosts):
    ips_to_query, host_to_ip = [], {}
    for h in hosts:
        try:
            ip = socket.gethostbyname(h)
            ips_to_query.append(ip)
            host_to_ip[h] = ip
        except: continue
    if not ips_to_query: return {}
    try:
        unique_ips = list(set(ips_to_query))[:BATCH_SIZE]
        url = "http://ip-api.com/batch?fields=status,query,countryCode,isp,proxy"
        res = requests.post(url, json=unique_ips, timeout=10).json()
        ip_map = {i['query']: i for i in res if i.get('status') == 'success'}
        return {h: ip_map[ip] for h, ip in host_to_ip.items() if ip in ip_map}
    except: return {}

def rename_server(link, info, index):
    flag = info.get('countryCode', 'UN')
    isp = info.get('isp', 'Unknown').split()[0].strip(',.')
    num = str(index).zfill(4)
    date = datetime.datetime.now().strftime("%d-%m-%Y")
    new_ps = f"[{flag}] {isp} | №{num} | {date}"
    if link.startswith('vless://'):
        return f"{link.split('#')[0]}#{new_ps}"
    if link.startswith('vmess://'):
        try:
            d = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            d['ps'] = new_ps
            return "vmess://" + base64.b64encode(json.dumps(d).encode('utf-8')).decode('utf-8')
        except: return link
    return link

def main():
    download_checker()
    raw_links_dict = {}
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            for url in [l.strip() for l in f if l.strip()]:
                try:
                    r = requests.get(url, timeout=10)
                    data = r.text
                    try: data = base64.b64decode(data.strip()).decode('utf-8')
                    except: pass
                    for line in data.splitlines():
                        if line.strip().startswith(('vless://', 'vmess://')):
                            raw_links_dict[line.strip().split('#')[0]] = line.strip()
                except: continue
    if not raw_links_dict: return
    with open("temp.txt", "w") as f: f.write("\n".join(raw_links_dict.values()))
    res = subprocess.run([CHECKER_PATH, "-u", "https://www.youtube.com", "-f", "temp.txt", "--format", "json"], capture_output=True, text=True)
    try:
        alive = sorted([n for n in json.loads(res.stdout) if n.get('delay', 0) > 0], key=lambda x: x['delay'])
    except: return
    final = []
    idx = 1
    for i in range(0, len(alive), BATCH_SIZE):
        chunk = alive[i:i+BATCH_SIZE]
        h_map = {parse_host(n['link']): n['link'] for n in chunk if parse_host(n['link'])}
        i_map = get_batch_ip_info(list(h_map.keys()))
        for n in chunk:
            info = i_map.get(parse_host(n['link']))
            if info and "Cloudflare" not in info.get('isp', ''):
                final.append(rename_server(n['link'], info, idx))
                idx += 1
        time.sleep(2)
    if final:
        with open(OUTPUT_FILE, "w") as f:
            f.write(base64.b64encode("\n".join(final).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
