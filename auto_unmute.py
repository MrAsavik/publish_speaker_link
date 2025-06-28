import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

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
    print("❌ Не найден config.json")
    exit(1)

# В памяти состояние диалогов для меню и фоновой задачи
state = {}
bg_task = None  # ссылка на фоновую задачу мониторинга

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
    lines = []
    for i, (label, _) in enumerate(chs.items(), start=1):
        mark = " (default)" if label == default else ""
        lines.append(f"{i}. {label}{mark}")
    return "\n".join(lines)

# ─── 3. Инициализация Telethon-клиента ──────────────────────────────────────
client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# ─── 4. Поиск и подготовка группового эфира ─────────────────────────────────
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
        print("ℹ️ Эфир не запущен в этом канале.")
        return None
    return InputGroupCall(call.id, call.access_hash)

# ─── 5. Мониторинг и авто-размут ─────────────────────────────────────────────
async def watch_and_unmute(call: InputGroupCall):
    seen = set()
    while True:
        try:
            resp = await client(GetGroupCallRequest(call=call, limit=200))
        except GroupcallInvalidError:
            # Эфир завершён, выйдем, чтобы background_watch заново искал эфир
            raise
        for p in resp.participants:
            uid = getattr(p.peer, "user_id", None)
            if not uid or uid in seen or not p.muted:
                continue
            try:
                ent = await client.get_entity(uid)
                await client(EditGroupCallParticipantRequest(call=call, participant=ent, muted=False))
                print(f"✅ Размутил {uid}")
                seen.add(uid)
            except errors.RPCError as e:
                print(f"❌ Не смог размутить {uid}: {e}")
        await asyncio.sleep(15)

# ─── 6. Обработчики меню (/start и управление каналами) ────────────────────
@client.on(events.NewMessage(pattern=r"^/start$"))
async def on_start(ev):
    chat = ev.chat_id
    state[chat] = {"step": "menu", "last": ev.message.id}
    cfg = load_config()
    menu = (
        "🛠 Главное меню:\n"
        "0. 🔄 В главное меню\n"
        "1. ➕ Добавить канал\n"
        "2. 📋 Список каналов\n"
        "3. 🗑 Удалить канал\n"
        "4. 🎯 Установить default\n"
        "Введите цифру (0–4):"
    )
    await ev.reply(menu)

@client.on(events.NewMessage(pattern=r"^[0-4]$"))
async def on_menu(ev):
    chat = ev.chat_id
    st = state.get(chat)
    if not st or st.get("step") != "menu":
        return
    choice = ev.text.strip()
    state[chat] = {"step": choice, "last": ev.message.id}
    cfg = load_config(); chs = cfg.get("channels", {})
    if choice == "0": return await on_start(ev)
    if choice == "1": return await ev.reply("🔐 Выберите тип канала:\n1. public\n2. private")
    if choice == "2":
        await ev.reply("📋 Список каналов:\n" + format_channels(cfg))
        return await on_start(ev)
    if choice == "3":
        if not chs: await ev.reply("⚠️ Нет каналов."); return await on_start(ev)
        return await ev.reply("🗑 Введите номер для удаления (0 — отмена):\n" + format_channels(cfg))
    if choice == "4":
        if not chs: await ev.reply("⚠️ Нет каналов."); return await on_start(ev)
        return await ev.reply("🎯 Введите номер default (0 — отмена):\n" + format_channels(cfg))

@client.on(events.NewMessage)
async def on_text(ev):
    chat = ev.chat_id; msg = ev.message.id; txt = ev.text.strip()
    st = state.get(chat)
    if not st or msg <= st.get("last", 0): return
    state[chat]["last"] = msg
    if txt == "0": return await on_start(ev)
    cfg = load_config(); chs = cfg.get("channels", {})
    step = st.get("step")
    # добавить public/private
    if step == "1":
        if txt not in ("1","2"): return await ev.reply("❌ Выберите 1 или 2")
        state[chat]["step"] = f"add_{'public' if txt=='1' else 'private'}"
        return await ev.reply("Введите @username метка" if txt=='1' else "Введите часть названия канала")
    if step == "add_public":
        parts = txt.split()
        if len(parts)!=2 or not parts[0].startswith("@"): return await ev.reply("❌ Формат: @username метка")
        user,label = parts
        try: ent = await client.get_entity(user)
        except: return await ev.reply(f"❌ Не найден {user}")
        chs[label] = {"id":ent.id,"hash":ent.access_hash}; cfg["channels"]=chs; save_config(cfg)
        await ev.reply(f"✅ Public {user} сохранён как {label}")
        return await on_start(ev)
    if step == "add_private":
        dialogs = await client.get_dialogs()
        cands = [d for d in dialogs if d.is_channel and txt.lower() in (d.name or "").lower()]
        if not cands: return await ev.reply("❌ Не найдено.")
        if len(cands)==1:
            d=cands[0]; ent=d.entity; label=d.name
            chs[label]={"id":ent.id,"hash":ent.access_hash}; cfg["channels"]=chs; save_config(cfg)
            await ev.reply(f"✅ Приватный {label} сохранён")
            return await on_start(ev)
        msg_text = "\n".join(f"{i+1}. {d.name}" for i,d in enumerate(cands))
        state[chat]["step"]="choose_private"; state[chat]["cands"]=cands
        return await ev.reply("Выберите номер (0 — отмена):\n"+msg_text)
    if step == "choose_private":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx = int(txt)-1
        if idx<0 or idx>=len(state[chat]["cands"]): return await ev.reply("❌ Неверный")
        d=state[chat]["cands"][idx]; ent=d.entity; label=d.name
        chs[label]={"id":ent.id,"hash":ent.access_hash}; cfg["channels"]=chs; save_config(cfg)
        await ev.reply(f"✅ Приватный {label} сохранён")
        return await on_start(ev)
    if step == "3":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx=int(txt)-1
        if idx<0 or idx>=len(chs): return await ev.reply("❌ Неверный")
        label=list(chs.keys())[idx]
        chs.pop(label); cfg["channels"]=chs; save_config(cfg)
        await ev.reply(f"🗑 Канал {label} удалён")
        return await on_start(ev)
    if step == "4":
        if not txt.isdigit(): return await ev.reply("❌ Номер")
        idx=int(txt)-1
        if idx<0 or idx>=len(chs): return await ev.reply("❌ Неверный")
        label=list(chs.keys())[idx]
        cfg["default"]=label; save_config(cfg)
        await ev.reply(f"🎯 Default установлен: {label}")
        return await on_start(ev)

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

# ─── 8. Запуск бота ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    client.start(phone=PHONE)
    print("🤖 Бот запущен, жду команд…")
    client.run_until_disconnected()
