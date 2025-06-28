Она очень простая: даёт вам возможность говорить. По умолчанию вы не можете говорить в эфире канала, пока не получите разрешение. Эта программа делает это автоматически новым участникам, как только эфир стартует.

🚦 Алгоритм работы
Генерация строки сессии
Перед первым запуском получите SESSION_STRING — строку авторизации без файлов:


from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID   = <ваш_api_id>
API_HASH = "<ваш_api_hash>"

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print(client.session.save())
Скопируйте вывевшуюся строку в .env → SESSION_STRING.

## 🔧 Возможности

* Поддержка приватных каналов (поиск/выбор)
* Автоматический мониторинг эфиров с авто-размутом участников
* Команды `/watch`, `/stop`, `/status` и админ-контроль (`ADMIN_IDS`)
* Метрики нагрузки: время итерации и число участников
* Автоперезапуск клиента при падении

---

## 📦 requirements.txt

```text
telethon>=1.24.0
python-dotenv>=0.21.0
```

---

## 🛠 .env‑пример

Создайте файл `.env` в корне проекта:

```
dotenv
API_ID=your_api_id
API_HASH=your_api_hash
PHONE=+71234567890
SESSION_NAME=voice_access_bot
SESSION_STRING=
```

* `CHROME_PROFILE_DIR` — путь к профилю Chrome с уже залогиненным Telegram Web
* `ADMIN_IDS` — список Telegram ID администраторов, которые могут менять конфиг и управлять мониторингом
* `AUTHORIZED_USERNAMES` — список Telegram username для команды `/scan_connect`

---

## 🚀 Установка

1. Клонируйте репозиторий.
2. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```
3. Создайте и настройте `.env` по примеру выше.


## 🧩 Работа приватного режима

1. `/start` → `➕ Добавить канал` → `2. private`
2. Введите часть названия или username канала
3. Выберите нужный из списка, если найдено несколько
4. Канал сохранится в `config.json` с типом `private`

---


## 🔒 Контроль доступа

* Команды `/watch`, `/stop`, `/status`, `/start` 
---

> По вопросам настройки и доработок обращайтесь к автору проекта. https://t.me/TopHelpLink
---
