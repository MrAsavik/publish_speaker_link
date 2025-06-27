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

# ─── Логирование ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Загрузка .env ─────────────────────────────────────────────────────────────
load_dotenv()
API_ID       = os.getenv("API_ID")
API_HASH     = os.getenv("API_HASH")
PHONE        = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")

if not all([API_ID, API_HASH, PHONE]):
    logger.error("Неполные креды: задайте API_ID, API_HASH и PHONE в .env")
    exit(1)

client      = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
CONFIG_PATH = Path("config.json")
DRAFT_PATH  = Path("draft_post.txt")

def load_config():
    if not CONFIG_PATH.exists() or not CONFIG_PATH.read_text().strip():
        CONFIG_PATH.write_text(json.dumps({"channels": {}}, indent=2), encoding="utf-8")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("channels", {})
    except json.JSONDecodeError:
        logger.warning("config.json повреждён — пересоздаю.")
        CONFIG_PATH.write_text(json.dumps({"channels": {}}, indent=2), encoding="utf-8")
        return {}

def save_config(channels: dict):
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump({"channels": channels}, f, indent=2)

async def main():
    await client.start(PHONE)

    channels = load_config()
    if not channels:
        logger.error("Нет каналов в config.json — сначала запустите setup_config.py")
        return

    # Меню управления метками
    while True:
        print("\nМеню:")
        print(" 1. Показать и выбрать канал")
        print(" 2. Удалить метку канала")
        print(" 3. Выход")
        choice = input("Ваш выбор (1-3): ").strip()
        if choice == "1":
            break
        elif choice == "2":
            keys = list(channels.keys())
            if not keys:
                print("Нечего удалять.")
                continue
            print("Метки каналов:")
            for i, label in enumerate(keys, 1):
                print(f" {i}. {label}")
            idx = input(f"Введите номер метки для удаления (1–{len(keys)}) или Enter для отмены: ").strip()
            if not idx:
                continue
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                label = keys[int(idx)-1]
                del channels[label]
                save_config(channels)
                logger.info("Метка '%s' удалена.", label)
            else:
                print("Неверный ввод.")
        elif choice == "3":
            await client.disconnect()
            return
        else:
            print("Неверный пункт, попробуйте снова.")

    # 1) Выбор канала
    print("\nДоступные каналы:")
    keys = list(channels.keys())
    for i, name in enumerate(keys, 1):
        print(f" {i}. {name}")
    idx = int(input("Выберите канал номером: ").strip()) - 1
    name = keys[idx]
    data = channels[name]
    channel = InputChannel(data["id"], data["hash"])

    # 2) Получение объекта эфира
    try:
        full = await client(GetFullChannelRequest(channel))
    except errors.RPCError as e:
        logger.error("Ошибка при получении канала: %s", e)
        return

    call = getattr(full.full_chat, "call", None)
    if not call:
        logger.info("Эфир не запущен в этом канале.")
        return

    logger.info("Эфир: id=%s, access_hash=%s", call.id, call.access_hash)

    # 3) Экспорт спикер-ссылки
    igc = InputGroupCall(call.id, call.access_hash)
    try:
        invite = await client(ExportGroupCallInviteRequest(igc, True))
    except errors.PublicChannelMissingError:
        logger.error("Канал должен быть публичным для экспорта ссылки.")
        return
    except errors.RPCError as e:
        logger.error("RPC-ошибка при экспорте: %s", e)
        return

    hsh = invite.link.split("=").pop()
    username = getattr(full.chats[0], "username", None)
    if not username:
        logger.error("У канала нет @username — сделайте канал публичным.")
        return

    # 4) Единственная рабочая ссылка
    voice_link = f"https://t.me/{username}?voicechat={hsh}"
    print("\n🔹 Рабочая ссылка:")
    print(f" • {voice_link}")

    # 5) Подготовка шаблона поста и черновика
    post_template = (
        "🎙 **Присоединяйтесь к эфиру прямо сейчас!**\n\n"
        f"• Голосовой чат:\n{voice_link}\n\n"
        "— Отредактируйте этот текст при необходимости."
    )
    DRAFT_PATH.write_text(post_template, encoding="utf-8")
    logger.info("Черновик сохранён в %s", DRAFT_PATH)

    # 6) Опциональное отложенное отправление
    if input("Запланировать публикацию через 1 час? (y/N): ").strip().lower() == 'y':
        send_time = datetime.utcnow() + timedelta(hours=1)
        await client.send_message(
            entity=channel,
            message=post_template,
            schedule=send_time
        )
        logger.info("Пост запланирован на %s UTC", send_time.strftime("%Y-%m-%d %H:%M"))

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
