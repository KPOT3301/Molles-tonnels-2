import requests
import base64
from datetime import datetime

URLS = [
    "ВСТАВЬ_СЮДА_СВОЮ_ССЫЛКУ"
]

output = []
seen = set()

for url in URLS:
    print("Проверяем:", url)

    try:
        r = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0"
        })

        raw = r.text.strip()

        print("Длина ответа:", len(raw))

        # Пробуем декодировать base64
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            print("Base64 успешно декодирован")
        except Exception:
            decoded = raw
            print("Base64 НЕ применялся")

        lines = decoded.splitlines()
        print("Строк после split:", len(lines))

        for line in lines:
            line = line.strip()
            if line.startswith(("vless://", "vmess://", "trojan://", "ss://", "hysteria://")):
                if line not in seen:
                    seen.add(line)
                    output.append(line)

    except Exception as e:
        print("Ошибка:", e)

print("Найдено серверов:", len(output))

header = f"""#profile-title:RUKPOTовыеТОННЕЛИRu
#subscription-userinfo: upload=0; download=0; total=0; expire=0
#profile-update-interval: 1
#support-url:RUKPOTовыеТОННЕЛИRu
#profile-web-page-url:RUKPOTовыеТОННЕЛИRu
#announce: АКТИВНЫХ {len(output)} | ОБНОВЛЕНО {datetime.now().strftime("%d-%m-%Y")}
"""

with open("Molestunnels.txt", "w", encoding="utf-8") as f:
    f.write(header + "\n".join(output))

print("Готово.")
