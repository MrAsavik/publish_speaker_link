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

# ─── Настройка логирования ─────────────────────────────────────────────────────
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

client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
CONFIG_PATH = Path("config.json")
DRAFT_PATH  = Path("draft_post.txt")

def load_config():
    # безопасная загрузка config.json
    if not CONFIG_PATH.exists() or not CONFIG_PATH.read_text().strip():
        CONFIG_PATH.write_text(json.dumps({"channels": {}}, indent=2), encoding="utf-8")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("channels", {})
    except json.JSONDecodeError:
        logger.warning("config.json повреждён — перезаписываю.")
        CONFIG_PATH.write_text(json.dumps({"channels": {}}, indent=2), encoding="utf-8")
        return {}

async def main():
    await client.start(PHONE)

    # 1) Выбор канала
    channels = load_config()
    if not channels:
        logger.error("Нет каналов в config.json — сначала запустите setup_config.py")
        return

    print("Доступные каналы:")
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

    # 4) Генерация двух рабочих ссылок
    https_link = f"https://t.me/{username}?voicechat={hsh}"
    tg_link    = f"tg://resolve?domain={username}&livestream={hsh}"
    print("\n🔹 Ссылки:")
    print(" 1) HTTPS-voicechat:", https_link)
    print(" 2) TG-livestream: ", tg_link)

    # 5) Подготовка шаблона поста и черновика
    post_template = (
        "🎙 **Присоединяйтесь к эфиру прямо сейчас!**\n\n"
        f"• Веб (голосовой чат):\n{https_link}\n\n"
        f"• Мобильный (livestream):\n{tg_link}\n\n"
        "— Отредактируйте этот текст при необходимости."
    )
    DRAFT_PATH.write_text(post_template, encoding="utf-8")
    logger.info("Черновик сохранён в %s", DRAFT_PATH)

    # 6) Опциональное отложенное отправление
    if input("Запланировать отправку через 1 час? (y/N): ").strip().lower() == 'y':
        send_time = datetime.utcnow() + timedelta(hours=1)
        await client.send_message(
            entity=channel,
            message=post_template,
            schedule=send_time    # ← используем `schedule`, а не `schedule_date`
        )
        logger.info("Пост запланирован на %s UTC", send_time.strftime("%Y-%m-%d %H:%M"))

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
