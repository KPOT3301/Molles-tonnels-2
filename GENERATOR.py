import requests
import base64
from datetime import datetime

URLS = [
    "ССЫЛКА_НА_ПОДПИСКУ_1",
    "ССЫЛКА_НА_ПОДПИСКУ_2"
]

output = []
seen = set()

for url in URLS:
    try:
        r = requests.get(url, timeout=20)
        content = r.text.strip()

        # пробуем base64
        try:
            content = base64.b64decode(content).decode("utf-8")
        except:
            pass

        lines = content.splitlines()

        print(f"{url} → строк: {len(lines)}")

        for line in lines:
            line = line.strip()
            if line.startswith(("vless://", "vmess://", "trojan://", "ss://", "hysteria://")):
                if line not in seen:
                    seen.add(line)
                    output.append(line)

    except Exception as e:
        print("Ошибка:", e)

header = f"""#profile-title:RUKPOTовыеТОННЕЛИRu
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:RUKPOTовыеТОННЕЛИRu
#profile-web-page-url:RUKPOTовыеТОННЕЛИRu
#announce: АКТИВНЫХ {len(output)} | ОБНОВЛЕНО {datetime.now().strftime("%d-%m-%Y")}
"""

with open("Molestunnels.txt", "w", encoding="utf-8") as f:
    f.write(header + "\n".join(output))

print("Готово. Добавлено серверов:", len(output))
