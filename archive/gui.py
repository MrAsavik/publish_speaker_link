import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

import PySimpleGUI as sg
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import ExportGroupCallInviteRequest
from telethon.tl.types import InputChannel, InputGroupCall

# ─── Логирование ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Загрузка .env ─────────────────────────────────────────────────────────────
load_dotenv()
API_ID       = os.getenv("API_ID")
API_HASH     = os.getenv("API_HASH")
PHONE        = os.getenv("PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "voice_access_bot")

# Пути
CONFIG_PATH = Path("config.json")
DRAFT_PATH  = Path("draft_post.txt")

# Инициализация Telethon-клиента
client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# ─── Функция генерации ссылки ─────────────────────────────────────────────────
async def gen_link_task(label, schedule_flag):
    channels = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("channels", {})
    if label not in channels:
        return None, f"Метка '{label}' не найдена в config.json."
    data = channels[label]
    peer = InputChannel(data["id"], data["hash"])
    # Подключаемся и получаем эфир
    await client.start(PHONE)
    try:
        full = await client(GetFullChannelRequest(peer))
    except errors.RPCError as e:
        return None, f"Ошибка при получении канала: {e}"
    call = getattr(full.full_chat, "call", None)
    if not call:
        return None, "Эфир не запущен в этом канале."
    igc = InputGroupCall(call.id, call.access_hash)
    try:
        invite = await client(ExportGroupCallInviteRequest(igc, True))
    except errors.PublicChannelMissingError:
        return None, "Канал должен быть публичным."
    except errors.RPCError as e:
        return None, f"Ошибка экспорта ссылки: {e}"
    hsh = invite.link.split("=").pop()
    username = getattr(full.chats[0], "username", None)
    if not username:
        return None, "У канала нет @username."
    link = f"https://t.me/{username}?voicechat={hsh}"
    # Сохраняем черновик
    post = (
        "🎙 **Присоединяйтесь к эфиру прямо сейчас!**\n\n"
        f"• Голосовой чат:\n{link}\n\n"
        "— Отредактируйте текст при необходимости."
    )
    DRAFT_PATH.write_text(post, encoding="utf-8")
    msg = f"Ссылка: {link}\nЧерновик: {DRAFT_PATH}"
    # Отложенная отправка при флаге
    if schedule_flag:
        send_time = datetime.utcnow() + timedelta(hours=1)
        await client.send_message(entity=peer, message=post, schedule=send_time)
        msg += f"\nОтправка запланирована на {send_time.strftime('%Y-%m-%d %H:%M')} UTC"
    await client.disconnect()
    return link, msg

# ─── Интерфейс PySimpleGUI ────────────────────────────────────────────────────
def main():
    # Загрузка меток из config.json
    try:
        channels = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("channels", {})
    except Exception:
        channels = {}
    layout = [
        [sg.Text("Метка канала:"), sg.Combo(list(channels.keys()), key="-LABEL-", size=(20,1))],
        [sg.Checkbox("Отложить на 1 час", key="-SCHED-")],
        [sg.Button("Сгенерировать"), sg.Button("Выход")],
        [sg.Multiline(size=(60,10), key="-OUTPUT-", disabled=True)]
    ]
    window = sg.Window("Voice Access Generator", layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "Выход"):
            break
        if event == "Сгенерировать":
            label = values['-LABEL-']
            schedule_flag = values['-SCHED-']
            if not label:
                window['-OUTPUT-'].update("Выберите метку канала!\n")
                continue
            window['-OUTPUT-'].update("Генерация...\n")
            # Запуск asyncio задачи
            link, msg = asyncio.run(gen_link_task(label, schedule_flag))
            window['-OUTPUT-'].update(msg + "\n")
    window.close()

if __name__ == "__main__":
    main()
