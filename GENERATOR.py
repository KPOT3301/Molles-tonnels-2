async def main():
    print("Reading sources...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            sources = [line.strip() for line in f if line.strip()]
    except:
        print("No sslist.txt found.")
        return

    # Дата ДД-ММ-ГГГГ
    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    update_date = moscow_time.strftime("%d-%m-%Y")

    async with aiohttp.ClientSession() as session:

        tasks = [fetch(session, url) for url in sources]
        results = await asyncio.gather(*tasks)

        print("Extracting VLESS configs...")

        all_configs = []
        for text in results:
            all_configs.extend(extract_vless(text))

        all_configs = list(set(all_configs))

        print(f"Total unique VLESS configs: {len(all_configs)}")

        semaphore = asyncio.Semaphore(CONCURRENCY)

        print("Checking servers (with latency)...")

        tasks = [
            check_server(cfg, semaphore, session)
            for cfg in all_configs
        ]

        checked = await asyncio.gather(*tasks)

    alive = [c for c in checked if c is not None]

    if not alive:
        print("WARNING: No alive configs found!")
        return

    # Сортировка по скорости (но без ограничения количества)
    alive.sort(key=lambda x: x["latency"])

    print(f"Total alive servers: {len(alive)}")

    formatted = []

    for idx, item in enumerate(alive, start=1):
        formatted.append(
            f'{item["config"]}#{item["flag"]} СЕРВЕР {idx:03d} | ОБНОВЛЕН {update_date}'
        )

    # -------------------- HEADERS --------------------

    HEADERS = [
        f"#profile-title:{PROFILE_TITLE}",
        "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
        "#profile-update-interval: 1",
        f"#support-url:{PROFILE_TITLE}",
        f"#profile-web-page-url:{PROFILE_TITLE}",
        f"#announce: 🚀 РАБОЧИХ {len(formatted)} | 📅 {update_date}"
    ]

    print("Writing files...")

    final_text = "\n".join(HEADERS + formatted)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_text)

    base64_data = base64.b64encode(final_text.encode()).decode()

    with open(BASE64_FILE, "w", encoding="utf-8") as f:
        f.write(base64_data)

    print("Done.")
