import os
import json
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall

# ─── Настройка логирования ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ─── Загрузка .env ─────────────────────────────────────────────────────────────
load_dotenv()
API_ID       = os.getenv("API_ID")
API_HASH     = os.getenv("API_HASH")
PHONE        = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")

if not all([API_ID, API_HASH, PHONE]):
    logger.error("Не заданы обязательные переменные окружения (API_ID, API_HASH, PHONE).")
    raise SystemExit(1)

client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
CONFIG_PATH = Path("config.json")

def load_config():
    if not CONFIG_PATH.exists() or not CONFIG_PATH.read_text().strip():
        default = {"channels": {}}
        CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if "channels" not in cfg or not isinstance(cfg["channels"], dict):
            cfg["channels"] = {}
        return cfg
    except json.JSONDecodeError:
        logger.warning("config.json повреждён — перезаписываю новую структуру.")
        default = {"channels": {}}
        CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default

async def main():
    await client.start(PHONE)

    # ─── Загрузка и проверка конфига ─────────────────────────────────────────────
    config   = load_config()
    channels = config["channels"]
    if not channels:
        logger.error("В config.json нет ни одного канала. Запустите setup_config.py.")
        return

    # ─── Выводим пронумерованный список каналов ──────────────────────────────────
    print("Доступные каналы:")
    keys = list(channels.keys())
    for i, name in enumerate(keys, 1):
        print(f" {i}. {name}")
    # выбор по индексу
    while True:
        idx_str = input("Выберите канал номером: ").strip()
        if idx_str.isdigit() and 1 <= int(idx_str) <= len(keys):
            key = keys[int(idx_str) - 1]
            break
        logger.error("Неправильный ввод — введите число от 1 до %d.", len(keys))

    data    = channels[key]
    channel = InputChannel(data["id"], data["hash"])

    # ─── Получаем полный объект канала и проверяем эфир ────────────────────────
    try:
        full     = await client(GetFullChannelRequest(channel))
    except errors.RPCError as e:
        logger.error("Ошибка при получении канала: %s", e)
        return

    call_obj = getattr(full.full_chat, "call", None)
    if not call_obj:
        logger.info("🚫 Эфир не запущен в этом канале.")
        return

    logger.info("✅ Эфир активен! id=%s, access_hash=%s", call_obj.id, call_obj.access_hash)

    # ─── Экспортируем спикер-ссылку ─────────────────────────────────────────────
    igc = InputGroupCall(call_obj.id, call_obj.access_hash)
    try:
        invite = await client(ExportGroupCallInviteRequest(igc, True))
    except errors.PublicChannelMissingError:
        logger.error("Нельзя экспортировать ссылку: канал должен быть публичным.")
        return
    except errors.RPCError as e:
        logger.error("RPC-ошибка при экспорте ссылки: %s", e)
        return

    raw         = invite.link
    invite_hash = raw.split("=").pop()
    username    = getattr(full.chats[0], "username", None)
    if not username:
        logger.error("Канал не имеет публичного @username — сделайте канал публичным.")
        return

    # ─── Генерация и пронумерованный вывод deep-link вариантов ──────────────────
    variants = [
        ("tg_universal",     f"tg://resolve?domain={username}&videochat={invite_hash}"),
        ("https_videochat",  f"https://t.me/{username}?videochat={invite_hash}"),
        ("https_voicechat",  f"https://t.me/{username}?voicechat={invite_hash}"),
        ("https_livestream", f"https://t.me/{username}?livestream={invite_hash}"),
        ("tg_voicechat",     f"tg://resolve?domain={username}&voicechat={invite_hash}"),
        ("tg_livestream",    f"tg://resolve?domain={username}&livestream={invite_hash}"),
    ]

    print("\n🔹 Варианты ссылок для тестирования:")
    for i, (label, url) in enumerate(variants, 1):
        print(f" {i}. {label}: {url}")

    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Выход по Ctrl+C")
