import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel

# 📥 Подгружаем переменные из .env
load_dotenv()
api_id       = int(os.getenv("API_ID"))
api_hash     = os.getenv("API_HASH")
phone        = os.getenv("PHONE")
session_name = os.getenv("SESSION_NAME", "voice_access_bot")

client = TelegramClient(session_name, api_id, api_hash)
config_path = Path('config.json')

async def main():
    await client.start(phone)

    config_path = Path('config.json')

    # Загрузка или инициализация конфига
    if config_path.exists() and config_path.read_text().strip():
        config = json.loads(config_path.read_text())
        if "channels" not in config:
            config["channels"] = {}
    else:
        config = {"channels": {}}
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print("Поисковый фильтр по названию канала:")
    query = input("Введите часть названия канала (или оставьте пустым — показать все): ").strip().lower()

    # Получаем все диалоги, фильтруем каналы
    dialogs = await client.get_dialogs()
    channels = [d.entity for d in dialogs if getattr(d.entity, 'broadcast', False)]
    
    # Фильтрация по query
    filtered = []
    for chan in channels:
        title = getattr(chan, 'title', '') or ''
        if not query or query in title.lower():
            filtered.append(chan)

    if not filtered:
        print("⚠️ Каналы не найдены по вашему запросу.")
        return

    # Выводим отфильтрованные каналы
    print("Найденные каналы:")
    for idx, chan in enumerate(filtered, start=1):
        title = getattr(chan, 'title', '') or "<без названия>"
        print(f" {idx}. {title} (id={chan.id})")

    choice = int(input("Выберите номер канала: ").strip())
    chan = filtered[choice - 1]
    channel_name = input("Введите метку для этого канала в config: ").strip()

    channel_id = chan.id
    channel_hash = chan.access_hash

    # Сохраняем в config.json (без данных по эфирy)
    config['channels'][channel_name] = {
        'id': channel_id,
        'hash': channel_hash
    }
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print(f"✔ Конфигурация канала '{channel_name}' сохранена в config.json.")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
