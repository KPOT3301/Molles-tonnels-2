def rename_server(link, index, total_count):
    """
    Ракетами помечаются 10% самых быстрых серверов.
    Остальные помечаются молниями.
    """
    num = str(index).zfill(4)
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Считаем порог для 10% (минимум 1 сервер всегда будет ракетой)
    threshold = max(1, int(total_count * 0.1))
    
    # Если индекс сервера входит в первые 10%, ставим ракету
    status_icon = "🚀" if index <= threshold else "⚡"
    
    clean_name = f"{status_icon} SERVER-{num} | {today}"
    
    if link.startswith('vless://'):
        base_part = link.split('#')[0]
        return f"{base_part}#{clean_name}"
    elif link.startswith('vmess://'):
        try:
            v_data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            v_data['ps'] = clean_name
            return "vmess://" + base64.b64encode(json.dumps(v_data).encode('utf-8')).decode('utf-8')
        except: return link
    return link

# В функции main() найди цикл формирования ссылок и замени его на этот:
    # 3. Переименование и запись в чистый ТЕКСТ
    if alive:
        server_count = len(alive) # Общее количество рабочих серверов
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            # Сначала пишем твой красивый заголовок
            f.write("\n".join(header) + "\n")
            
            # Затем пишем ключи, передавая общее количество для расчета 10%
            for i, node in enumerate(alive, 1):
                new_link = rename_server(node['link'], i, server_count)
                f.write(f"{new_link}\n")
        print(f"✅ Подписка обновлена: {server_count} серверов. Из них 10% с ракетами!")
