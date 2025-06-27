import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall

# ─── Конфигурация и логирование ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
API_ID       = os.getenv("API_ID")
API_HASH     = os.getenv("API_HASH")
PHONE        = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")

if not all([API_ID, API_HASH, PHONE]):
    logger.error("API_ID, API_HASH и PHONE должны быть заданы в .env")
    exit(1)

CONFIG_PATH = Path("config.json")
DRAFT_PATH  = Path("draft_post.txt")
client      = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# ─── Функции работы с config.json ──────────────────────────────────────────────
def load_channels():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"channels": {}}, indent=2), encoding="utf-8")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg.get("channels", {})

def save_channels(channels):
    CONFIG_PATH.write_text(json.dumps({"channels": channels}, indent=2), encoding="utf-8")

# ─── Асинхронные задачи ────────────────────────────────────────────────────────
async def async_add_channel(username, label):
    await client.connect()
    try:
        entity = await client.get_entity(username)
    except Exception as e:
        return False, f"Не удалось найти канал @{username}: {e}"
    channels = load_channels()
    channels[label] = {"id": entity.id, "hash": entity.access_hash}
    save_channels(channels)
    await client.disconnect()
    return True, f"Канал @{username} сохранён как '{label}'"

async def async_generate_link(label, schedule=False):
    await client.connect()
    channels = load_channels()
    if label not in channels:
        await client.disconnect()
        return None, f"Метка '{label}' не найдена"
    data = channels[label]
    peer = InputChannel(data["id"], data["hash"])
    # Получаем эфир
    try:
        full = await client(GetFullChannelRequest(peer))
    except errors.RPCError as e:
        await client.disconnect()
        return None, f"Ошибка получения канала: {e}"
    call = getattr(full.full_chat, "call", None)
    if not call:
        await client.disconnect()
        return None, "Эфир не запущен"
    # Экспорт ссылки
    igc = InputGroupCall(call.id, call.access_hash)
    try:
        inv = await client(ExportGroupCallInviteRequest(igc, True))
    except errors.PublicChannelMissingError:
        await client.disconnect()
        return None, "Канал должен быть публичным"
    except errors.RPCError as e:
        await client.disconnect()
        return None, f"Ошибка экспорта: {e}"
    invite_hash = inv.link.split("=").pop()
    username = getattr(full.chats[0], "username", None)
    if not username:
        await client.disconnect()
        return None, "У канала нет @username"
    link = f"https://t.me/{username}?voicechat={invite_hash}"
    # Черновик
    post = (
        "🎙 **Присоединяйтесь к эфиру прямо сейчас!**\n\n"
        f"• Голосовой чат:\n{link}\n\n"
        "— Отредактируйте текст при необходимости."
    )
    DRAFT_PATH.write_text(post, encoding="utf-8")
    msg = f"Ссылка: {link}\nЧерновик: {DRAFT_PATH}"
    # Планирование
    if schedule:
        send_time = datetime.utcnow() + timedelta(hours=1)
        await client.send_message(entity=peer, message=post, schedule=send_time)
        msg += f"\nОтправка запланирована на {send_time.strftime('%Y-%m-%d %H:%M')} UTC"
    await client.disconnect()
    return link, msg

# ─── CLI-меню ──────────────────────────────────────────────────────────────────
def main():
    while True:
        print("\nГлавное меню:")
        print(" 1. Добавить канал")
        print(" 2. Список каналов")
        print(" 3. Удалить канал")
        print(" 4. Сгенерировать ссылку")
        print(" 5. Выход")
        choice = input("Ваш выбор (1-5): ").strip()
        if choice == '1':
            user = input("Username канала (без @): ").strip()
            label = input("Метка для канала: ").strip()
            ok, msg = asyncio.run(async_add_channel(user, label))
            print(msg)
        elif choice == '2':
            chans = load_channels()
            if not chans:
                print("Нет каналов")
            else:
                for lbl, cfg in chans.items():
                    print(f"- {lbl}: id={cfg['id']}, hash={cfg['hash']}")
        elif choice == '3':
            chans = load_channels()
            keys = list(chans.keys())
            for i, lbl in enumerate(keys, 1): print(f" {i}. {lbl}")
            idx = input("Номер для удаления: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                del chans[keys[int(idx)-1]]
                save_channels(chans)
                print("Удалено")
            else:
                print("Неверный ввод")
        elif choice == '4':
            chans = load_channels()
            labels = list(chans.keys())
            for i, lbl in enumerate(labels, 1): print(f" {i}. {lbl}")
            idx = input("Выберите канал: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(labels):
                label = labels[int(idx)-1]
                sched = input("Отложить на 1 час? (y/N): ").strip().lower() == 'y'
                link, msg = asyncio.run(async_generate_link(label, sched))
                print(msg)
            else:
                print("Неверный выбор")
        elif choice == '5':
            break
        else:
            print("Неверный пункт меню")

if __name__ == '__main__':
    main()
