import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import traceback
import time

from telethon import TelegramClient, events, errors
from telethon.errors.rpcerrorlist import GroupcallInvalidError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import GetGroupCallRequest, EditGroupCallParticipantRequest
from telethon.tl.types import InputChannel, InputGroupCall

# ─── 1. Загрузка окружения и конфигураций ───────────────────────────────────
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
    default_cfg = {"default": "", "channels": {}}
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(default_cfg, f, ensure_ascii=False, indent=4)
    print("ℹ️ Сгенерирован новый config.json")

# В памяти состояние диалогов и фоновые задачи
state = {}
bg_task = None
is_unmuting = False  # флаг, что размут запущен

# ─── 2. Утилиты для работы с конфигом ──────────────────────────────────────
def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)

def format_channels(cfg):
    chs = cfg.get("channels", {})
    default = cfg.get("default")
    if not chs:
        return "⚠️ Нет сохранённых каналов."
    return "\n".join(f"{i}. {label}" + (" (default)" if label==default else "")
                      for i,(label,_) in enumerate(chs.items(),1))

# ─── 3. Инициализация Telethon-клиента ──────────────────────────────────────
client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# ─── 4. Поиск группового эфира ──────────────────────────────────────────────
async def get_group_call() -> InputGroupCall:
    cfg = load_config()
    label = cfg.get("default")
    chs = cfg.get("channels", {})
    if not label or label not in chs:
        print("❌ Неправильный default в config.json")
        return None
    data = chs[label]
    peer = InputChannel(data["id"], data["hash"])
    try:
        full = await client(GetFullChannelRequest(peer))
    except errors.RPCError as e:
        print(f"❌ Ошибка GetFullChannelRequest: {e}")
        return None
    call = getattr(full.full_chat, "call", None)
    if not call:
        return None
    return InputGroupCall(call.id, call.access_hash)

# ─── 5. Мониторинг и авто-размут ─────────────────────────────────────────────
async def watch_and_unmute(call: InputGroupCall):
    global is_unmuting
    seen = set()
    is_unmuting = True
    try:
        while True:
            try:
                resp = await client(GetGroupCallRequest(call=call, limit=200))
            except GroupcallInvalidError:
                raise
            for p in resp.participants:
                uid = getattr(p.peer, "user_id", None)
                if not uid or uid in seen or not p.muted:
                    continue
                try:
                    ent = await client.get_entity(uid)
                    await client(EditGroupCallParticipantRequest(call=call,participant=ent,muted=False))
                    print(f"✅ Размутил {uid}")
                    seen.add(uid)
                except errors.RPCError as e:
                    print(f"❌ Не смог размутить {uid}: {e}")
            await asyncio.sleep(15)
    finally:
        is_unmuting = False

# ─── 6. Хендлер /watch и /stop с учётом флага ────────────────────────────────
@client.on(events.NewMessage(pattern=r"^/(watch|stop)$"))
async def on_watch_stop(ev):
    global bg_task
    cmd = ev.text[1:]
    if cmd == "watch":
        if is_unmuting or (bg_task and not bg_task.done()):
            return await ev.reply("⚠️ Мониторинг уже запущен.")
        await ev.reply("👀 Запускаю мониторинг эфиров…")
        async def background_watch():
            while True:
                try:
                    call = await get_group_call()
                    if call:
                        await ev.reply("🎉 Эфир найден, начинаю размут…")
                        await watch_and_unmute(call)
                    else:
                        await asyncio.sleep(30)
                except GroupcallInvalidError:
                    await ev.reply("ℹ️ Эфир завершился, ожидаю следующего…")
                    await asyncio.sleep(30)
                except Exception as e:
                    print(f"❌ Ошибка фонового мониторинга: {e}")
                    await asyncio.sleep(30)
        bg_task = client.loop.create_task(background_watch())
    else:
        if not bg_task or bg_task.done():
            return await ev.reply("⚠️ Мониторинг не запущен.")
        bg_task.cancel()
        await ev.reply("🛑 Остановил мониторинг эфиров.")

# ─── 7. Новый хендлер /watch и /stop ────────────────────────────────────────
@client.on(events.NewMessage(pattern=r"^/(watch|stop)$"))
async def on_watch_stop(ev):
    global bg_task
    cmd = ev.text[1:]
    if cmd == "watch":
        if bg_task and not bg_task.done():
            return await ev.reply("⚠️ Мониторинг уже запущен.")
        await ev.reply("👀 Запускаю мониторинг эфиров…")
        async def background_watch():
            while True:
                try:
                    call = await get_group_call()
                    if call:
                        await ev.reply("🎉 Эфир найден, начинаю размут…")
                        await watch_and_unmute(call)
                    else:
                        await asyncio.sleep(30)
                except GroupcallInvalidError:
                    await ev.reply("ℹ️ Эфир завершился, ожидаю следующего…")
                    await asyncio.sleep(30)
                except Exception as e:
                    print(f"❌ Ошибка фонового мониторинга: {e}")
                    await asyncio.sleep(30)
        bg_task = client.loop.create_task(background_watch())
    else:  # stop
        if not bg_task or bg_task.done():
            return await ev.reply("⚠️ Мониторинг не запущен.")
        bg_task.cancel()
        await ev.reply("🛑 Остановил мониторинг эфиров.")

# ─── 8. Автоперезапуск клиента ──────────────────────────────────────────────
async def main_loop():
    await client.start(phone=PHONE)
    print("🤖 Бот запущен, жду команд…")
    await client.run_until_disconnected()

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main_loop())
        except Exception:
            traceback.print_exc()
            print("❌ Клиент упал, перезапускаем через 5 секунд…")
            time.sleep(5)
