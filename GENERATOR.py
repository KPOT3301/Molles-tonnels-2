import requests

URL = "ТВОЯ_ССЫЛКА_СЮДА"

r = requests.get(URL, headers={
    "User-Agent": "Mozilla/5.0"
}, timeout=30)

print("STATUS:", r.status_code)
print("LENGTH:", len(r.text))
print("FIRST 300 CHARS:")
print(r.text[:300])
