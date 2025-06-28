# auto_unmute.py

import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from telethon import functions, types, errors
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import GetGroupCallRequest, EditGroupCallParticipantRequest
from telethon.tl.types import InputChannel, InputGroupCall, InputPeerUser

# ─── 1. Загрузка окружения ───────────────────────────────────────────────────
dotenv_path = find_dotenv(usecwd=True)
if not dotenv_path:
    print("❌ Не найден .env рядом со скриптом")
    exit(1)
load_dotenv(dotenv_path)

API_ID       = os.getenv("API_ID")
API_HASH     = os.getenv("API_HASH")
PHONE        = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "auto_unmute")
CONFIG_PATH  = Path("config.json")

if not all([API_ID, API_HASH, PHONE]):
    print("❌ В .env должны быть API_ID, API_HASH и PHONE")
    exit(1)
if not CONFIG_PATH.exists():
    print("❌ Не найден config.json")
    exit(1)

# ─── 2. Чтение конфига каналов ────────────────────────────────────────────────
with open(CONFIG_PATH, encoding="utf-8") as f:
    cfg = json.load(f)
default_label = cfg.get("default")
channels      = cfg.get("channels", {})
if not default_label or default_label not in channels:
    print("❌ Неправильный default в config.json")
    exit(1)

ch = channels[default_label]
channel_peer = InputChannel(ch["id"], ch["hash"])

# ─── 3. Инициализация Telethon-клиента ──────────────────────────────────────
client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# ─── 4. Получаем InputGroupCall ─────────────────────────────────────────────
async def get_group_call() -> InputGroupCall:
    try:
        full = await client(GetFullChannelRequest(channel_peer))
    except errors.RPCError as e:
        print(f"❌ Ошибка GetFullChannelRequest: {e}")
        return None

    call = getattr(full.full_chat, "call", None)
    if not call:
        print("ℹ️ Эфир не запущен в этом канале.")
        return None

    return InputGroupCall(call.id, call.access_hash)

# ─── 5. Мониторинг и авто-unmute ────────────────────────────────────────────
async def watch_and_unmute(call):
    seen = set()
    while True:
        resp = await client(GetGroupCallRequest(call=call, limit=200))
        for part in resp.participants:
            # 1) Получаем user_id
            uid = getattr(part.peer, "user_id", None)
            if not uid or uid in seen or not part.muted:
                continue

            try:
                # 2) Получаем полный Entity пользователя (с access_hash)
                user_entity = await client.get_entity(uid)
                # 3) Вызываем запрос, передавая именно Entity
                await client(functions.phone.EditGroupCallParticipantRequest(
                    call=call,
                    participant=user_entity,    # Entity автоматически превращается в InputPeer
                    muted=False
                ))
                print(f"✅ Размутил {uid}")
                seen.add(uid)

            except errors.RPCError as e:
                # Любые RPC-ошибки здесь
                print(f"❌ Не смог размутить {uid}: {e}")

        await asyncio.sleep(15)
# ─── 6. Основной запуск ─────────────────────────────────────────────────────
async def main():
    await client.start(phone=PHONE)
    print("🤖 Telegram-клиент запущен. Проверяем эфир…")
    call = await get_group_call()
    if not call:
        await client.disconnect()
        return

    await watch_and_unmute(call)
    # (скрипт здесь никогда не завершится)

if __name__ == "__main__":
    asyncio.run(main())
 