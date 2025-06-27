import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone    import ExportGroupCallInviteRequest
from telethon.tl.types               import InputChannel, InputGroupCall
from web_export import get_private_channel_link

# ─── Чтение настроек ────────────────────────────────────────────────────────────
load_dotenv()
API_ID       = int(os.getenv("API_ID", 0))
API_HASH     = os.getenv("API_HASH", "")
PHONE        = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")
CONFIG_PATH  = Path("config.json")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ─── Состояния диалога и «точки входа» ────────────────────────────────────────
# Для каждого chat_id храним: шаг и ID последнего меню-сообщения
state = {}  # chat_id → {"step": str, "last_msg_id": int}

# ─── Утилиты для config.json ──────────────────────────────────────────────────
def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"channels": {}, "default": None}, indent=2), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# ─── Генерация спикер-ссылки ───────────────────────────────────────────────────
async def export_link(label):
    cfg = load_config()
    chs = cfg["channels"]
    if label not in chs:
        return None, f"❌ Метка «{label}» не найдена."
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
        inv = await client(ExportGroupCallInviteRequest(igc, True))
    except errors.PublicChannelMissingError:
        return None, "❌ Канал должен быть публичным."
    except errors.RPCError as e:
        return None, f"❌ Ошибка экспорта: {e}"
    hsh = inv.link.split("=").pop()
    uname = getattr(full.chats[0], "username", None)
    if not uname:
        return None, "❌ У канала нет @username."
    return f"https://t.me/{uname}?voicechat={hsh}", None

# ─── Главное меню ───────────────────────────────────────────────────────────────
@client.on(events.NewMessage(pattern=r"^/start$"))
async def on_start(ev):
    chat = ev.chat_id
    # Сохраняем шаг и точку входа
    state[chat] = {"step": "menu", "last_msg_id": ev.message.id}
    text = (
        "🛠 *Главное меню*:\n"
        "0. 🔄 В главное меню\n"
        "1. ➕ Добавить канал\n"
        "2. 📋 Список каналов\n"
        "3. 🗑 Удалить канал\n"
        "4. 🎯 Установить канал по умолчанию\n"
        "5. 🔗 Сгенерировать ссылку (по default)\n"
        "6. 📩 Опубликовать пост в default\n"
        "7. 🚪 Выход\n\n"
        "Введите цифру (0–7):"
    )
    await ev.reply(text, parse_mode="md")

# ─── Обработка цифр меню ────────────────────────────────────────────────────────
@client.on(events.NewMessage(pattern=r"^[0-7]$"))
async def on_number(ev):
    chat   = ev.chat_id
    msg_id = ev.message.id
    st     = state.get(chat)
    # Игнорировать, если не в menu или старое сообщение
    if not st or st["step"] != "menu" or msg_id <= st["last_msg_id"]:
        return

    choice = int(ev.text)
    cfg    = load_config()

    # Обновим точку входа на этом меню-сообщении
    state[chat] = {"step": "menu", "last_msg_id": msg_id}

    if choice == 0:
        return await on_start(ev)

    if choice == 1:
        state[chat] = {"step": "add", "last_msg_id": msg_id}
        return await ev.reply("Введите через пробел: `username метка`\n0 — отмена", parse_mode="md")

    if choice == 2:
        chs = cfg["channels"]
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
        else:
            lines = "\n".join(f"- {lbl}" for lbl in chs)
            await ev.reply(f"📦 *Сохранённые каналы*:\n{lines}", parse_mode="md")
        return await on_start(ev)

    if choice == 3:
        chs = cfg["channels"]
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
            return await on_start(ev)
        menu = "\n".join(f"{i+1}. {lbl}" for i,lbl in enumerate(chs))
        state[chat] = {"step": "del_select", "last_msg_id": msg_id}
        return await ev.reply(f"🗑 Введите номер для удаления (0 — отмена):\n{menu}", parse_mode="md")

    if choice == 4:
        chs = cfg["channels"]
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
            return await on_start(ev)
        menu = "\n".join(f"{i+1}. {lbl}" for i,lbl in enumerate(chs))
        state[chat] = {"step": "setdef", "last_msg_id": msg_id}
        return await ev.reply(f"🎯 Введите номер default (0 — отмена):\n{menu}", parse_mode="md")

    if choice == 5:
        default = cfg.get("default")
        if not default:
            await ev.reply("❌ Default не задан. Сначала пункт 4.")
        else:
            try:
                # Пробуем через Web-автоматизацию
                link = get_private_channel_link(
                    username=cfg["channels"][default]["username"],
                    profile_dir="C:/Users/you/AppData/Local/Google/Chrome/User Data"
                )
            except Exception as e:
                await ev.reply(f"❌ Не удалось экспортировать через Web: {e}")
            else:
                await ev.reply(f"🔹 Ссылка (Web):\n{link}")
        return await on_start(ev)

    if choice == 6:
        default = cfg.get("default")
        if not default:
            await ev.reply("❌ Default не задан.")
        else:
            link, err = await export_link(default)
            if err:
                await ev.reply(err)
            else:
                post = f"🎙 Присоединяйтесь:\n{link}"
                data = cfg["channels"][default]
                peer = InputChannel(data["id"], data["hash"])
                await client.send_message(peer, post)
                await ev.reply("📩 Пост опубликован.")
        return await on_start(ev)

    if choice == 7:
        state.pop(chat, None)
        return await ev.reply("👋 До встречи! Для нового меню — /start")

# ─── Обработка текстовых ответов для подсостояний ───────────────────────────────
@client.on(events.NewMessage)
async def on_text(ev):
    chat   = ev.chat_id
    msg_id = ev.message.id
    st     = state.get(chat)
    if not st or msg_id <= st["last_msg_id"]:
        return  # не наш шаг или старое сообщение

    cfg = load_config()
    txt = ev.text.strip()

    # Отмена
    if txt == "0" and st["step"] in ("add", "del_select", "setdef"):
        return await on_start(ev)

    # Добавление канала
    if st["step"] == "add":
        parts = txt.split()
        if len(parts) != 2:
            return await ev.reply(
                "❌ Формат неверен! Введите:\n`username метка`\n0 — отмена", parse_mode="md"
            )
        user, label = parts
        try:
            ent = await client.get_entity(user)
        except Exception as e:
            return await ev.reply(f"❌ Не найден @{user}: {e}\n0 — отмена")
        cfg["channels"][label] = {"id": ent.id, "hash": ent.access_hash}
        save_config(cfg)
        await ev.reply(f"✅ @{user} сохранён как «{label}»")
        return await on_start(ev)

    # Удаление канала
    if st["step"] == "del_select":
        labels = list(cfg["channels"].keys())
        if not txt.isdigit():
            return await ev.reply("❌ Введите номер (цифру)!\n0 — отмена")
        idx = int(txt)
        if not (1 <= idx <= len(labels)):
            return await ev.reply(f"❌ Номер вне диапазона (1–{len(labels)})!\n0 — отмена")
        removed = labels[idx-1]
        cfg["channels"].pop(removed)
        save_config(cfg)
        await ev.reply(f"🗑 Канал «{removed}» удалён")
        return await on_start(ev)

    # Установка default
    if st["step"] == "setdef":
        labels = list(cfg["channels"].keys())
        if not txt.isdigit():
            return await ev.reply("❌ Введите цифру!\n0 — отмена")
        idx = int(txt)
        if not (1 <= idx <= len(labels)):
            return await ev.reply(f"❌ Номер вне диапазона (1–{len(labels)})!\n0 — отмена")
        cfg["default"] = labels[idx-1]
        save_config(cfg)
        await ev.reply(f"🎯 Default установлен: «{cfg['default']}»")
        return await on_start(ev)

# ─── Запуск ────────────────────────────────────────────────────────────────────
async def main():
    await client.start(phone=PHONE)
    print("🤖 UserBot запущен. Ожидаю /start …")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
