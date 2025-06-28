# userbot_with_menu.py

import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import (
    GetGroupCallRequest,
    EditGroupCallParticipantRequest
)
from telethon.tl.types import InputChannel, InputGroupCall, InputPeerUser

# ─── Load environment and config ───────────────────────────────────────────
load_dotenv()
API_ID       = int(os.getenv("API_ID", 0))
API_HASH     = os.getenv("API_HASH", "")
PHONE        = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")
CONFIG_PATH  = Path("config.json")

if not (API_ID and API_HASH and PHONE):
    print("❌ В .env должны быть API_ID, API_HASH и PHONE")
    exit(1)
if not CONFIG_PATH.exists():
    print("❌ Не найден config.json")
    exit(1)

# ─── State and background task ─────────────────────────────────────────────
state = {}  # per-chat menu state
monitor_task = None  # background auto-unmute task

# ─── Telethon client ───────────────────────────────────────────────────────
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ─── Config loader/saver ───────────────────────────────────────────────────
def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# ─── Format saved channels for menu ────────────────────────────────────────
def format_channels(cfg):
    chs = cfg.get("channels", {})
    default = cfg.get("default")
    if not chs:
        return "⚠️ Нет каналов."
    lines = []
    for i, (lbl, _) in enumerate(chs.items(), start=1):
        mark = " (default)" if lbl == default else ""
        lines.append(f"{i}. {lbl}{mark}")
    return "\n".join(lines)

# ─── Export speaker link via Telethon ─────────────────────────────────────
async def export_link(label: str):
    cfg = load_config()
    chs = cfg.get("channels", {})
    if label not in chs:
        return None, f"❌ Метка '{label}' не найдена."
    data = chs[label]
    peer = InputChannel(data["id"], data["hash"])
    try:
        full = await client(GetFullChannelRequest(peer))
    except errors.RPCError as e:
        return None, f"❌ Ошибка получения канала: {e}"
    call = getattr(full.full_chat, "call", None)
    if not call:
        return None, "❌ Эфир не запущен."
    igc = InputGroupCall(call.id, call.access_hash)
    try:
        inv = await client(
            ExportGroupCallInviteRequest(igc, can_self_unmute=True)
        )
    except errors.ChatAdminRequiredError:
        return None, "❌ Бот не администратор с правами управления эфирами."
    except errors.RPCError as e:
        return None, f"❌ Ошибка экспорта: {e}"
    return inv.link, None

# ─── Retrieve current InputGroupCall ─────────────────────────────────────
async def get_group_call():
    cfg = load_config()
    default = cfg.get("default")
    data = cfg.get("channels", {}).get(default)
    if not data:
        return None
    peer = InputChannel(data["id"], data["hash"])
    try:
        full = await client(GetFullChannelRequest(peer))
    except errors.RPCError:
        return None
    call = getattr(full.full_chat, "call", None)
    if not call:
        return None
    return InputGroupCall(call.id, call.access_hash)

# ─── Background auto-unmute task ─────────────────────────────────────────
async def watch_and_unmute(call: InputGroupCall):
    me = await client.get_me()
    seen = {me.id}
    print(f"👀 Monitoring call id={call.id}, skipping self id={me.id}")
    while True:
        try:
            resp = await client(GetGroupCallRequest(call=call, limit=200))
            for part in resp.participants:
                uid = getattr(part.peer, "user_id", None)
                if not uid or uid in seen or not part.muted:
                    continue
                try:
                    user = await client.get_entity(uid)
                    name = getattr(user, "username", None) or getattr(user, "first_name", str(uid))
                    await client(
                        EditGroupCallParticipantRequest(
                            call=call,
                            participant=user,
                            muted=False
                        )
                    )
                    print(f"✅ Unmuted {uid} ({name})")
                    seen.add(uid)
                except errors.RPCError as e:
                    print(f"❌ Failed to unmute {uid}: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            await asyncio.sleep(10)

# ─── Menu event handlers ──────────────────────────────────────────────────
@client.on(events.NewMessage(pattern=r"^/start$"))
async def on_start(ev):
    chat = ev.chat_id
    state[chat] = {"step":"menu", "last_id":ev.message.id}
    menu = (
        "🛠 Главное меню:\n"
        "0. 🔄 В меню\n"
        "1. ➕ Добавить канал\n"
        "2. 📋 Список каналов\n"
        "3. 🗑 Удалить\n"
        "4. 🎯 Установить default\n"
        "5. 🔗 Сгенерировать ссылку\n"
        "6. 📩 Опубликовать в default\n"
        "7. 🚪 Выход\n"
        "8. 🚨 Auto-unmute\n"
        "Введите 0–8:"  
    )
    await ev.reply(menu)

@client.on(events.NewMessage(pattern=r"^[0-8]$"))
async def on_menu(ev):
    chat = ev.chat_id
    st = state.get(chat)
    if not st or st.get('step')!='menu': return
    choice = ev.text.strip()
    cfg = load_config()
    state[chat] = {'step':choice, 'last_id':ev.message.id}

    if choice=='0':
        return await on_start(ev)
    elif choice=='1':
        await ev.reply("Введите @username метка")
    elif choice=='2':
        await ev.reply("📋 " + format_channels(cfg))
        return await on_start(ev)
    elif choice=='3':
        await ev.reply("🗑 Введите номер для удаления:\n"+format_channels(cfg))
    elif choice=='4':
        await ev.reply("🎯 Введите номер default:\n"+format_channels(cfg))
    elif choice=='5':
        default = cfg.get('default')
        if not default:
            await ev.reply("❌ Default не задан")
            return await on_start(ev)
        link,err = await export_link(default)
        await ev.reply(err or f"🔗 {link}")
        return await on_start(ev)
    elif choice=='6':
        default = cfg.get('default')
        if not default:
            await ev.reply("❌ Default не задан")
            return await on_start(ev)
        link,err = await export_link(default)
        if err:
            await ev.reply(err)
        else:
            data=cfg['channels'][default]
            peer=InputChannel(data['id'],data['hash'])
            await client.send_message(peer, f"🎙 Эфир: {link}")
            await ev.reply("📩 Опубликовано")
        return await on_start(ev)
    elif choice=='7':
        return await ev.reply("👋 Пока!")
    elif choice=='8':
        call = await get_group_call()
        if not call:
            return await ev.reply("❌ Эфир не идет")
        global monitor_task
        if monitor_task and not monitor_task.done():
            return await ev.reply("⚠️ Auto-unmute уже запущен")
        monitor_task = asyncio.create_task(watch_and_unmute(call))
        return await ev.reply("🚨 Auto-unmute запущен")

# Further steps (add/delete/default) omitted for brevity, integrate similarly

async def main():
    await client.start(phone=PHONE)
    print("🤖 Bot started")
    await client.run_until_disconnected()

if __name__=='__main__':
    asyncio.run(main())
