import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall

# ─── Загрузка настроек из .env ────────────────────────────────────────────────
load_dotenv()  # читает API_ID, API_HASH, PHONE, SESSION_NAME из .env
api_id       = int(os.getenv("API_ID"))
api_hash     = os.getenv("API_HASH")
phone        = os.getenv("PHONE")
session_name = os.getenv("SESSION_NAME", "voice_access_bot")

client = TelegramClient(session_name, api_id, api_hash)

async def main():
    await client.start(phone)

    # ─── Чтение списка каналов из config.json ────────────────────────────────────
    cfg      = json.loads(Path("config.json").read_text())
    channels = cfg["channels"]
    print("Доступные каналы:", list(channels.keys()))
    key      = input("Выберите канал: ").strip()
    data     = channels[key]

    # ─── Формируем InputChannel для запросов ────────────────────────────────────
    channel = InputChannel(data["id"], data["hash"])

    # ─── Получаем полный объект канала, чтобы взять текущий эфир ───────────────
    full     = await client(GetFullChannelRequest(channel))
    call_obj = full.full_chat.call
    if not call_obj:
        print("🚫 Эфир не запущен в этом канале.")
        await client.disconnect()
        return

    # ─── Диагностика: выводим данные об эфире ───────────────────────────────────
    print("✅ Эфир активен!")
    print(f"  • call.id         = {call_obj.id}")
    print(f"  • call.access_hash= {call_obj.access_hash}")

    # ─── Экспортируем ссылку с правом сразу говорить ─────────────────────────────
    igc    = InputGroupCall(call_obj.id, call_obj.access_hash)
    invite = await client(ExportGroupCallInviteRequest(igc, True))
    raw    = invite.link                  # пример: 'https://t.me/c/123456/abcdef'
    hsh    = raw.split("=").pop()         # оставляем только хеш

    # ─── Генерируем deep-link для мобильного клиента ───────────────────────────
    username     = full.chats[0].username
    video_link   = f"https://t.me/{username}?videochat={hsh}"
    voice_link   = f"https://t.me/{username}?voicechat={hsh}"
    livestream   = f"https://t.me/{username}?livestream={hsh}"

    print("\n🚀 Ссылки на эфир:")
    print("▶ videochat link:  ", video_link)
    print("▶ voicechat link:  ", voice_link)
    print("▶ livestream link: ", livestream)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
