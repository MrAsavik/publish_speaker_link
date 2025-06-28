# Хорошо реализовано урпваление конфигом. Но не выполяет пставленную задачу
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall

# Load environment variables
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")
CONFIG_PATH = Path("config.json")

# Validate credentials
if not API_ID or not API_HASH or not PHONE:
    print("❌ Ошибка: в .env должны быть заданы API_ID, API_HASH и PHONE")
    exit(1)

# Initialize client
client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
# State per chat: { step: str, last_msg_id: int, cands?: list }
state = {}

# Configuration load/save

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"channels": {}, "default": None}, indent=2), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# Export speaker link via Telethon
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
        inv = await client(ExportGroupCallInviteRequest(igc, can_self_unmute=True))
    except errors.ChatAdminRequiredError:
        return None, "❌ Бот не администратор с правами управления эфирами."
    except errors.RPCError as e:
        return None, f"❌ Ошибка экспорта: {e}"
    return inv.link, None

# Helper to list channels

def format_channels(cfg):
    chs = cfg.get("channels", {})
    default = cfg.get("default")
    if not chs:
        return "⚠️ Нет сохранённых каналов."
    lines = []
    for i, (label, _) in enumerate(chs.items(), start=1):
        mark = " (default)" if label == default else ""
        lines.append(f"{i}. {label}{mark}")
    return "\n".join(lines)

# Telegram event handlers

@client.on(events.NewMessage(pattern=r"^/start$"))
async def on_start(ev):
    chat = ev.chat_id
    state[chat] = {"step": "menu", "last_msg_id": ev.message.id}
    menu = (
        "🛠 Главное меню:\n"
        "0. 🔄 В главное меню\n"
        "1. ➕ Добавить канал\n"
        "2. 📋 Список каналов\n"
        "3. 🗑 Удалить канал\n"
        "4. 🎯 Установить default\n"
        "5. 🔗 Сгенерировать ссылку\n"
        "6. 📩 Опубликовать в default\n"
        "7. 🚪 Выход\n"
        "Введите цифру (0–7):"
    )
    await ev.reply(menu)

@client.on(events.NewMessage(pattern=r"^[0-7]$"))
async def on_menu(ev):
    chat = ev.chat_id
    st = state.get(chat)
    # Only handle menu if current step is 'menu'
    if not st or st.get("step") != "menu":
        return
    choice = ev.text.strip()
    cfg = load_config()
    chs = cfg.get("channels", {})
    state[chat] = {"step": choice, "last_msg_id": ev.message.id}

    if choice == "0":
        return await on_start(ev)
    if choice == "1":
        await ev.reply("🔐 Выберите тип канала:\n1. public\n2. private")
    elif choice == "2":
        await ev.reply("📋 Список каналов:\n" + format_channels(cfg))
        return await on_start(ev)
    elif choice == "3":
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
            return await on_start(ev)
        await ev.reply("🗑 Введите номер для удаления (0 — отмена):\n" + format_channels(cfg))
    elif choice == "4":
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
            return await on_start(ev)
        await ev.reply("🎯 Введите номер default (0 — отмена):\n" + format_channels(cfg))
    elif choice == "5":
        default = cfg.get("default")
        if not default:
            await ev.reply("❌ Default не задан.")
            return await on_start(ev)
        link, err = await export_link(default)
        await ev.reply(err or f"🔗 Ссылка на эфир (спикер): {link}")
        return await on_start(ev)
    elif choice == "6":
        default = cfg.get("default")
        if not default:
            await ev.reply("❌ Default не задан.")
            return await on_start(ev)
        link, err = await export_link(default)
        if err:
            await ev.reply(err)
        else:
            data = chs[default]
            peer = InputChannel(data["id"], data["hash"])
            await client.send_message(peer, f"🎙 Эфир: {link}")
            await ev.reply("📩 Пост опубликован.")
        return await on_start(ev)
    else:
        await ev.reply("👋 До встречи!")

@client.on(events.NewMessage)
async def on_text(ev):
    chat = ev.chat_id
    msg_id = ev.message.id
    txt = ev.text.strip()
    st = state.get(chat)
    # Ignore if not in step or old
    if not st or msg_id <= st.get("last_msg_id", 0):
        return
    # Reset last_msg
    st["last_msg_id"] = msg_id

    # Cancel to menu
    if txt == "0":
        return await on_start(ev)

    cfg = load_config()
    chs = cfg.get("channels", {})
    step = st["step"]

    # Step 1: choose type
    if step == "1":
        if txt not in ("1", "2"): return await ev.reply("❌ Выберите 1 или 2")
        st["step"] = f"add_{'public' if txt=='1' else 'private'}"
        return await ev.reply("Введите @username метка" if txt=='1' else "Введите часть названия канала")

    # Step add_public
    if step == "add_public":
        parts = txt.split()
        if len(parts) != 2 or not parts[0].startswith("@"): return await ev.reply("❌ Формат: @username метка")
        user, label = parts
        try:
            ent = await client.get_entity(user)
        except Exception:
            return await ev.reply(f"❌ Не найден {user}")
        chs[label] = {"id": ent.id, "hash": ent.access_hash}
        cfg["channels"] = chs; save_config(cfg)
        await ev.reply(f"✅ Public {user} сохранён как {label}")
        return await on_start(ev)

    # Step add_private
    if step == "add_private":
        dialogs = await client.get_dialogs()
        cands = [d for d in dialogs if d.is_channel and txt.lower() in (d.name or "").lower()]
        if not cands: return await ev.reply("❌ Не найдено.")
        if len(cands) == 1:
            d = cands[0]; ent = d.entity; label = d.name
            chs[label] = {"id": ent.id, "hash": ent.access_hash}
            cfg["channels"] = chs; save_config(cfg)
            await ev.reply(f"✅ Приватный {label} сохранён")
            return await on_start(ev)
        msg = "\n".join(f"{i+1}. {d.name}" for i, d in enumerate(cands))
        st["step"] = "choose_private"
        st["cands"] = cands
        return await ev.reply("Выберите номер (0 — отмена):\n" + msg)

    # Step choose_private
    if step == "choose_private":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx = int(txt) - 1
        if idx < 0 or idx >= len(st["cands"]): return await ev.reply("❌ Неверный")
        d = st["cands"][idx]; ent = d.entity; label = d.name
        chs[label] = {"id": ent.id, "hash": ent.access_hash}
        cfg["channels"] = chs; save_config(cfg)
        await ev.reply(f"✅ Приватный {label} сохранён")
        return await on_start(ev)

    # Step delete
    if step == "3":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx = int(txt) - 1
        if idx < 0 or idx >= len(chs): return await ev.reply("❌ Неверный")
        label = list(chs.keys())[idx]
        chs.pop(label)
        cfg["channels"] = chs; save_config(cfg)
        await ev.reply(f"🗑 Канал {label} удалён")
        return await on_start(ev)

    # Step default
    if step == "4":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx = int(txt) - 1
        if idx < 0 or idx >= len(chs): return await ev.reply("❌ Неверный")
        label = list(chs.keys())[idx]
        cfg["default"] = label; save_config(cfg)
        await ev.reply(f"🎯 Default установлен: {label}")
        return await on_start(ev)

async def main():
    await client.start(phone=PHONE)
    print("🤖 Voice Access Bot запущен...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
