import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall
from web_export import get_private_channel_link

load_dotenv()
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")
CONFIG_PATH = Path("config.json")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
state = {}

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"channels": {}, "default": None}, indent=2), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

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

@client.on(events.NewMessage(pattern=r'^scan_connect$'))
async def on_scan_connect(ev):
    sender = await ev.get_sender()
    if not sender or not sender.username == "MrAsavik":
        return await ev.reply("❌ Доступ запрещён.")

    from web_export import test_connection

    profile_path = "./chrome_profile"  # замени на актуальный путь
    await ev.reply("🔄 Проверка подключения к Telegram Web...")

    ok = test_connection(profile_path)
    if ok:
        await ev.reply("✅ Подключение к Telegram Web успешно.")
    else:
        await ev.reply("❌ Не удалось подключиться к Telegram Web.")


@client.on(events.NewMessage(pattern=r"^/start$"))
async def on_start(ev):
    chat = ev.chat_id
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

@client.on(events.NewMessage(pattern=r"^[0-7]$"))
async def on_number(ev):
    chat = ev.chat_id
    msg_id = ev.message.id
    st = state.get(chat)
    if not st or st["step"] != "menu" or msg_id <= st["last_msg_id"]:
        return

    choice = int(ev.text)
    cfg = load_config()
    state[chat] = {"step": "menu", "last_msg_id": msg_id}

    if choice == 0:
        return await on_start(ev)

    if choice == 1:
        state[chat] = {"step": "add_type", "last_msg_id": msg_id}
        return await ev.reply("🔐 Выберите тип канала:\n1. public (открытый)\n2. private (закрытый)", parse_mode="md")

    if choice == 2:
        chs = cfg["channels"]
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
        else:
            lines = "\n".join(f"- {lbl} ({chs[lbl].get('type', 'unknown')})" for lbl in chs)
            await ev.reply(f"📦 *Сохранённые каналы*:\n{lines}", parse_mode="md")
        return await on_start(ev)

    if choice == 3:
        chs = cfg["channels"]
        if not chs:
            await ev.reply("⚠️ Нет каналов.")
            return await on_start(ev)
        menu = "\n".join(f"{i+1}. {lbl}" for i,lbl in enumerate(chs))
        state[chat] = {
            "step": "del_select",
            "last_msg_id": msg_id,
            "labels": list(chs.keys())
        }
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
            data = cfg["channels"][default]
            if data.get("type") == "private":
                try:
                    link = get_private_channel_link(
                        username=data["username"],
                        profile_dir="C:/Users/you/AppData/Local/Google/Chrome/User Data"
                    )
                except Exception as e:
                    await ev.reply(f"❌ Ошибка Web: {e}")
                else:
                    await ev.reply(f"🔗 Ссылка (private):\n{link}")
            else:
                link, err = await export_link(default)
                if err:
                    await ev.reply(err)
                else:
                    await ev.reply(f"🔗 Ссылка:\n{link}")
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

@client.on(events.NewMessage)
async def on_text(ev):
    chat = ev.chat_id
    msg_id = ev.message.id
    st = state.get(chat)
    if not st or msg_id <= st["last_msg_id"]:
        return

    cfg = load_config()
    txt = ev.text.strip()

    if txt == "0" and st["step"] in ("add_type", "add_public", "add_private", "del_select", "setdef"):
        return await on_start(ev)

    if st["step"] == "add_private":
        # Поиск по имени
        candidates = []
        dialogs = await client.get_dialogs()
        for d in dialogs:
            if not d.is_channel:
                continue
            name = d.name.lower()
            username = (getattr(d.entity, "username", "") or "").lower()
            if txt.lower() in name or txt.lower() in username:
                candidates.append(d)

        if not candidates:
            return await ev.reply("❌ Не найдено каналов по этому имени.")

        if len(candidates) == 1:
            d = candidates[0]
            ent = d.entity
            label = d.name
            cfg["channels"][label] = {
                "id": ent.id, "hash": ent.access_hash, "type": "private", "username": label
            }
            save_config(cfg)
            return await ev.reply(f"✅ Приватный канал сохранён как «{label}»")

        # если несколько — показать и спросить номер
        lines = "\n".join(f"{i+1}. {d.name}" for i, d in enumerate(candidates))
        state[chat] = {"step": "add_private_choice", "last_msg_id": msg_id, "list": candidates}
        return await ev.reply(f"🔍 Найдено несколько:\n{lines}\nВведите номер (0 — отмена)", parse_mode="md")
    
    if st["step"] == "add_private_choice":
        lst = st.get("list", [])
        if not txt.isdigit():
            return await ev.reply("❌ Введите номер (0 — отмена)")
        idx = int(txt)
        if idx == 0:
            return await on_start(ev)
        if not (1 <= idx <= len(lst)):
            return await ev.reply(f"❌ Неверный номер (1–{len(lst)})")
        d = lst[idx - 1]
        ent = d.entity
        label = d.name
        cfg["channels"][label] = {
            "id": ent.id, "hash": ent.access_hash, "type": "private", "username": label
        }
        save_config(cfg)
        await ev.reply(f"✅ Приватный канал сохранён как «{label}»")
        return await on_start(ev)


    if st["step"] == "add_public":
        parts = txt.split()
        if len(parts) != 2:
            return await ev.reply("❌ Формат неверен! Введите:\n`username метка`\n0 — отмена", parse_mode="md")
        user, label = parts
        try:
            ent = await client.get_entity(user)
        except Exception as e:
            return await ev.reply(f"❌ Не найден @{user}: {e}")
        cfg["channels"][label] = {"id": ent.id, "hash": ent.access_hash, "type": "public", "username": user}
        save_config(cfg)
        await ev.reply(f"✅ @{user} сохранён как «{label}» (public)")
        return await on_start(ev)

    if st["step"] == "add_private":
        if not txt.isdigit():
            return await ev.reply("❌ Введите номер канала (0 — отмена)")
        idx = int(txt)
        chans = st.get("private_list", [])
        if not (1 <= idx <= len(chans)):
            return await ev.reply(f"❌ Неверный номер (1–{len(chans)})")
        ent = chans[idx-1].entity
        label = chans[idx-1].name
        cfg["channels"][label] = {
            "id": ent.id, "hash": ent.access_hash, "type": "private", "username": label
        }
        save_config(cfg)
        await ev.reply(f"✅ Приватный канал сохранён как «{label}»")
        return await on_start(ev)

    if st["step"] == "setdef":
        labels = list(cfg["channels"].keys())
        if not txt.isdigit():
            return await ev.reply("❌ Введите цифру!\n0 — отмена")
        idx = int(txt)
        if not (1 <= idx <= len(labels)):
            return await ev.reply(f"❌ Неверный номер (1–{len(labels)})")
        cfg["default"] = labels[idx-1]
        save_config(cfg)
        await ev.reply(f"🎯 Default установлен: «{cfg['default']}»")
        return await on_start(ev)

async def main():
    await client.start(phone=PHONE)
    print("🤖 UserBot запущен. Ожидаю /start …")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
